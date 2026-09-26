#!/usr/bin/env python3
"""
Portable Living Memory, Transcript Sync & Hybrid Search Engine (memory.py)

Zero mandatory third-party dependencies (runs on Python 3.10+ stdlib `sqlite3`,
`urllib.request`, `json`, `math`, with optional `numpy` acceleration).

Features & Improvements:
1. Portable relative-path keys (`rel_path`) so moving the repo across machines,
   containers, or custom harnesses never invalidates the SQLite index.
2. Pluggable zero-corp embedding providers (`MEMORY_EMBED_PROVIDER`: `auto`,
   `ollama`, `gemini`, `openai`, `cmd`, or `none`) with batch embedding and
   automatic graceful degradation to pure SQLite FTS5 BM25 when offline.
3. Enhanced FTS5 (`porter unicode61` with `-_.` token preservation) and column
   weighting (`doc_title` 8x, `section_title` 5x, `rel_path` 3x, `content` 1x).
4. Document-tier & recency weighting in Reciprocal Rank Fusion (RRF) so curated
   `pinned` / `note` / `doc` entries outrank raw `transcript` logs.
5. Hierarchical markdown chunking (`##` and `###` breadcrumbs) + paragraph-aware
   sub-chunking for long sections with exact 1-indexed line number preservation
   and match-centered snippet previews.
6. Multi-harness transcript ingestion (`sync-transcripts`) supporting OpenAI /
   Anthropic / generic JSONL, Claude Code JSONL, and Gemini JSONL formats.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sqlite3
import struct
import subprocess
import time
import urllib.error
import urllib.request

# Directory layout (relative to agent/skill root)
AGENT_ROOT = Path(
    os.environ.get("AGENT_ROOT", Path(__file__).resolve().parent.parent)
).resolve()
MEMORY_FILE = AGENT_ROOT / "MEMORY.md"
WAKE_FILE = AGENT_ROOT / "WAKE.md"
NOTES_DIR = AGENT_ROOT / "notes"
DOCS_DIR = AGENT_ROOT / "docs"
TRANSCRIPTS_DIR = AGENT_ROOT / "transcripts"
INDEX_DIR = AGENT_ROOT / ".index"
DB_PATH = INDEX_DIR / "memory.db"

# Tier multipliers for RRF scoring
TIER_WEIGHTS = {
    "pinned": 1.30,
    "note": 1.15,
    "doc": 1.15,
    "transcript": 0.85,
}


def pack_floats(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack_floats(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_db_connection() -> sqlite3.Connection:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS indexed_files (
            rel_path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            sha256 TEXT NOT NULL,
            chunk_count INTEGER NOT NULL,
            indexed_at REAL NOT NULL
        );
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rel_path TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            date TEXT NOT NULL,
            doc_title TEXT NOT NULL,
            section_title TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB
        );
    """)
    con.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
            content,
            section_title,
            doc_title,
            rel_path,
            content='chunks',
            content_rowid='id',
            tokenize="porter unicode61 tokenchars '-_.'"
        );
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO fts_chunks(rowid, content, section_title, doc_title, rel_path)
            VALUES (new.id, new.content, new.section_title, new.doc_title, new.rel_path);
        END;
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO fts_chunks(fts_chunks, rowid, content, section_title, doc_title, rel_path)
            VALUES('delete', old.id, old.content, old.section_title, old.doc_title, old.rel_path);
        END;
    """)


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"^activate\s+\w+\s*", "", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:45] if text else "session"


# ---------------------------------------------------------------------------
# Pluggable Zero-Corp Embedding Backends
# ---------------------------------------------------------------------------


def detect_embed_provider() -> str:
    provider = os.environ.get("MEMORY_EMBED_PROVIDER", "auto").lower().strip()
    if provider != "auto":
        return provider
    if os.environ.get("MEMORY_EMBED_CMD"):
        return "cmd"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OLLAMA_EMBED_MODEL") or os.environ.get("OLLAMA_HOST"):
        return "ollama"
    return "none"


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Batch-embed texts using the active provider, or return [None, ...] if offline/disabled."""
    if not texts:
        return []

    provider = detect_embed_provider()
    if provider == "none":
        return [None] * len(texts)

    truncated = [t[:10000] for t in texts]

    try:
        if provider == "ollama":
            host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
            model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
            payload = json.dumps({"model": model, "input": truncated}).encode("utf-8")
            req = urllib.request.Request(
                f"{host}/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embeddings", [None] * len(texts))

        if provider == "openai":
            api_key = os.environ["OPENAI_API_KEY"]
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            model = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
            payload = json.dumps({"model": model, "input": truncated}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/embeddings",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in items]

        if provider == "gemini":
            api_key = os.environ["GEMINI_API_KEY"]
            model = os.environ.get("GEMINI_EMBED_MODEL", "models/text-embedding-004")
            if not model.startswith("models/"):
                model = f"models/{model}"
            requests_list = [
                {"model": model, "content": {"parts": [{"text": t}]}}
                for t in truncated
            ]
            payload = json.dumps({"requests": requests_list}).encode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents?key={api_key}"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [e["values"] for e in data.get("embeddings", [])]

        if provider == "cmd":
            cmd_template = shlex.split(os.environ["MEMORY_EMBED_CMD"])
            results: list[list[float] | None] = []
            for t in truncated:
                proc = subprocess.run(
                    [*cmd_template, t],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if proc.returncode == 0:
                    raw = proc.stdout.strip().lstrip("[").rstrip("]").replace(",", " ")
                    results.append([float(x) for x in raw.split()])
                else:
                    results.append(None)
            return results

    except Exception:
        # Graceful degradation to FTS5 when offline or on transient API error
        return [None] * len(texts)

    return [None] * len(texts)


# ---------------------------------------------------------------------------
# Hierarchical Markdown Chunking with Line-Number Preservation
# ---------------------------------------------------------------------------


def split_large_chunk(
    section: str, start_line: int, lines: list[str], max_lines: int = 110
) -> list[dict]:
    """Sub-chunk long markdown sections on paragraph boundaries while preserving exact line numbers."""
    if len(lines) <= max_lines:
        content = "".join(lines).strip()
        if not content:
            return []
        return [{
            "section": section,
            "start_line": start_line,
            "end_line": start_line + len(lines) - 1,
            "content": content,
        }]

    sub_chunks = []
    curr_lines: list[str] = []
    curr_start = start_line
    in_fence = False

    for offset, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence

        curr_lines.append(line)
        is_blank = (stripped == "") and not in_fence

        if len(curr_lines) >= max_lines and is_blank:
            content = "".join(curr_lines).strip()
            if content:
                sub_chunks.append({
                    "section": section,
                    "start_line": curr_start,
                    "end_line": start_line + offset,
                    "content": content,
                })
            curr_lines = []
            curr_start = start_line + offset + 1

    if curr_lines:
        content = "".join(curr_lines).strip()
        if content:
            sub_chunks.append({
                "section": section,
                "start_line": curr_start,
                "end_line": start_line + len(lines) - 1,
                "content": content,
            })

    return sub_chunks


def parse_markdown(file_path: Path) -> tuple[str, str, list[dict]]:
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

    fname = file_path.name
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
    doc_date = date_match.group(1) if date_match else datetime.fromtimestamp(
        file_path.stat().st_mtime
    ).strftime("%Y-%m-%d")

    doc_title = fname
    doc_title_set = False
    raw_sections: list[tuple[str, int, list[str]]] = []

    h2_title = ""
    h3_title = ""
    curr_lines: list[str] = []
    start_line = 1
    in_code_block = False

    def current_breadcrumb() -> str:
        if h2_title and h3_title:
            return f"{h2_title} > {h3_title}"
        return h2_title or h3_title or "Overview"

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block

        if not in_code_block:
            if line.startswith("# ") and not doc_title_set:
                doc_title = line[2:].strip()
                doc_title_set = True

            if line.startswith("## ") or line.startswith("### "):
                if curr_lines:
                    raw_sections.append((current_breadcrumb(), start_line, curr_lines))
                if line.startswith("## "):
                    h2_title = line[3:].strip()
                    h3_title = ""
                else:
                    h3_title = line[4:].strip()
                curr_lines = [line]
                start_line = i
                continue

        curr_lines.append(line)

    if curr_lines:
        raw_sections.append((current_breadcrumb(), start_line, curr_lines))

    valid_chunks: list[dict] = []
    for section_name, s_line, s_lines in raw_sections:
        for sub in split_large_chunk(section_name, s_line, s_lines):
            body_lines = [
                l for l in sub["content"].split("\n") if not l.strip().startswith("#")
            ]
            body_text = "".join(body_lines).strip()
            if len(body_text) >= 25 or len(sub["content"]) >= 80:
                valid_chunks.append(sub)

    return doc_date, doc_title, valid_chunks


# ---------------------------------------------------------------------------
# Indexing & Search
# ---------------------------------------------------------------------------


def collect_disk_files() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    if MEMORY_FILE.exists():
        files.append((MEMORY_FILE, "pinned"))
    if NOTES_DIR.exists():
        for p in sorted(NOTES_DIR.glob("*.md")):
            files.append((p, "note"))
    if DOCS_DIR.exists():
        for p in sorted(DOCS_DIR.glob("*.md")):
            files.append((p, "doc"))
    if TRANSCRIPTS_DIR.exists():
        for p in sorted(TRANSCRIPTS_DIR.glob("*.md")):
            files.append((p, "transcript"))
    return files


def index_files(
    force: bool = False, backfill_embeddings: bool = False, verbose: bool = True
) -> dict:
    con = get_db_connection()
    init_db(con)

    existing_files = {
        row["rel_path"]: row
        for row in con.execute("SELECT * FROM indexed_files").fetchall()
    }

    all_disk_files = collect_disk_files()
    disk_rel_paths = {p.relative_to(AGENT_ROOT).as_posix() for p, _ in all_disk_files}

    # Remove deleted files
    deleted_paths = set(existing_files.keys()) - disk_rel_paths
    for rel_path in deleted_paths:
        with con:
            con.execute("DELETE FROM chunks WHERE rel_path = ?", (rel_path,))
            con.execute("DELETE FROM indexed_files WHERE rel_path = ?", (rel_path,))

    files_to_process: list[tuple[Path, str, str, float, str]] = []
    for path, doc_type in all_disk_files:
        rel_path = path.relative_to(AGENT_ROOT).as_posix()
        mtime = path.stat().st_mtime
        sha256 = compute_sha256(path)

        if force or rel_path not in existing_files:
            files_to_process.append((path, rel_path, doc_type, mtime, sha256))
        else:
            prev = existing_files[rel_path]
            if prev["mtime"] != mtime or prev["sha256"] != sha256:
                files_to_process.append((path, rel_path, doc_type, mtime, sha256))

    new_chunks_count = 0
    for idx, (path, rel_path, doc_type, mtime, sha256) in enumerate(files_to_process, 1):
        doc_date, doc_title, parsed_chunks = parse_markdown(path)
        if verbose:
            print(
                f"[{idx}/{len(files_to_process)}] Indexing {rel_path} ({len(parsed_chunks)} chunks)..."
            )

        con.execute("DELETE FROM chunks WHERE rel_path = ?", (rel_path,))

        if not parsed_chunks:
            con.execute(
                """
                INSERT OR REPLACE INTO indexed_files (rel_path, mtime, sha256, chunk_count, indexed_at)
                VALUES (?, ?, ?, 0, unixepoch())
                """,
                (rel_path, mtime, sha256),
            )
            continue

        embed_payloads = [
            f"Date: {doc_date}\nDocument: {doc_title}\nSection: {c['section']}\nPath: {rel_path}\n\n{c['content']}"
            for c in parsed_chunks
        ]
        embeddings = embed_texts(embed_payloads)

        for c, emb in zip(parsed_chunks, embeddings):
            emb_bytes = pack_floats(emb) if emb else None
            con.execute(
                """
                INSERT INTO chunks (
                    rel_path, doc_type, date, doc_title,
                    section_title, start_line, end_line, content, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rel_path,
                    doc_type,
                    doc_date,
                    doc_title,
                    c["section"],
                    c["start_line"],
                    c["end_line"],
                    c["content"],
                    emb_bytes,
                ),
            )

        con.execute(
            """
            INSERT OR REPLACE INTO indexed_files (rel_path, mtime, sha256, chunk_count, indexed_at)
            VALUES (?, ?, ?, ?, unixepoch())
            """,
            (rel_path, mtime, sha256, len(parsed_chunks)),
        )
        new_chunks_count += len(parsed_chunks)

    backfilled = 0
    if backfill_embeddings and detect_embed_provider() != "none":
        missing = con.execute(
            "SELECT id, date, doc_title, section_title, rel_path, content FROM chunks WHERE embedding IS NULL"
        ).fetchall()
        if missing:
            payloads = [
                f"Date: {r['date']}\nDocument: {r['doc_title']}\nSection: {r['section_title']}\nPath: {r['rel_path']}\n\n{r['content']}"
                for r in missing
            ]
            embs = embed_texts(payloads)
            for r, emb in zip(missing, embs):
                if emb:
                    con.execute(
                        "UPDATE chunks SET embedding = ? WHERE id = ?",
                        (pack_floats(emb), r["id"]),
                    )
                    backfilled += 1

    con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    total_chunks = con.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
    con.close()

    return {
        "updated_files": len(files_to_process),
        "deleted_files": len(deleted_paths),
        "new_chunks": new_chunks_count,
        "backfilled_embeddings": backfilled,
        "total_chunks": total_chunks,
        "provider": detect_embed_provider(),
        "status": "indexed" if (files_to_process or deleted_paths or backfilled) else "up_to_date",
    }


def recency_multiplier(date_str: str) -> float:
    """Gentle recency boost (up to +10% for today, decaying over 90 days)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        days_old = max(0.0, (datetime.now() - dt).days)
        return 1.0 + 0.10 * math.exp(-days_old / 45.0)
    except Exception:
        return 1.0


def semantic_search(
    con: sqlite3.Connection,
    query: str,
    top_k: int = 5,
    doc_type: str | None = None,
) -> list[dict]:
    q_embs = embed_texts([query])
    if not q_embs or not q_embs[0]:
        return []
    q_vec = q_embs[0]

    sql = """
        SELECT id, rel_path, doc_type, date, doc_title, section_title,
               start_line, end_line, content, embedding
        FROM chunks
        WHERE embedding IS NOT NULL
    """
    params: list = []
    if doc_type and doc_type != "all":
        sql += " AND doc_type = ?"
        params.append(doc_type)

    rows = con.execute(sql, params).fetchall()
    if not rows:
        return []

    scored = []
    for r in rows:
        vec = unpack_floats(r["embedding"])
        sim = cosine_similarity(q_vec, vec)
        scored.append((sim, r))

    scored.sort(key=lambda x: -x[0])
    results = []
    for sim, r in scored[:top_k]:
        abs_path = str((AGENT_ROOT / r["rel_path"]).resolve())
        results.append({
            "id": r["id"],
            "file_path": abs_path,
            "rel_path": r["rel_path"],
            "doc_type": r["doc_type"],
            "date": r["date"],
            "doc_title": r["doc_title"],
            "section_title": r["section_title"],
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "content": r["content"],
            "score": float(sim),
            "match_type": "semantic",
        })
    return results


def keyword_search(
    con: sqlite3.Connection,
    query: str,
    top_k: int = 5,
    doc_type: str | None = None,
) -> list[dict]:
    clean_query = re.sub(r"[^\w\s\-\.\/:]", " ", query).strip()
    if not clean_query:
        return []

    tokens = [t for t in clean_query.split() if t]
    if not tokens:
        return []

    # Combine phrase match (if multi-token) with AND/OR token matches
    or_clause = " OR ".join(f'"{t}"' for t in tokens)
    if len(tokens) > 1:
        and_clause = " AND ".join(f'"{t}"' for t in tokens)
        fts_match = f"({and_clause}) OR ({or_clause})"
    else:
        fts_match = or_clause

    # Column weights: content=1.0, section_title=5.0, doc_title=8.0, rel_path=3.0
    sql = """
        SELECT c.id, c.rel_path, c.doc_type, c.date, c.doc_title,
               c.section_title, c.start_line, c.end_line, c.content,
               bm25(fts_chunks, 1.0, 5.0, 8.0, 3.0) AS rank
        FROM fts_chunks f
        JOIN chunks c ON f.rowid = c.id
        WHERE fts_chunks MATCH ?
    """
    params: list = [fts_match]
    if doc_type and doc_type != "all":
        sql += " AND c.doc_type = ?"
        params.append(doc_type)

    sql += " ORDER BY rank ASC LIMIT ?"
    params.append(top_k)

    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []

    results = []
    for r in rows:
        abs_path = str((AGENT_ROOT / r["rel_path"]).resolve())
        results.append({
            "id": r["id"],
            "file_path": abs_path,
            "rel_path": r["rel_path"],
            "doc_type": r["doc_type"],
            "date": r["date"],
            "doc_title": r["doc_title"],
            "section_title": r["section_title"],
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "content": r["content"],
            "score": float(-r["rank"]),
            "match_type": "keyword",
        })
    return results


def hybrid_search(
    con: sqlite3.Connection,
    query: str,
    top_k: int = 5,
    doc_type: str | None = None,
    rrf_k: int = 60,
) -> list[dict]:
    sem_results = semantic_search(con, query, top_k=top_k * 3, doc_type=doc_type)
    key_results = keyword_search(con, query, top_k=top_k * 3, doc_type=doc_type)

    rrf_scores: dict[int, float] = {}
    chunk_map: dict[int, dict] = {}

    for rank, hit in enumerate(sem_results):
        cid = hit["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
        chunk_map[cid] = hit

    for rank, hit in enumerate(key_results):
        cid = hit["id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
        if cid not in chunk_map:
            chunk_map[cid] = hit

    # Apply tier weight (pinned > note/doc > transcript) and gentle recency decay
    for cid, hit in chunk_map.items():
        tier_w = TIER_WEIGHTS.get(hit["doc_type"], 1.0)
        rec_w = recency_multiplier(hit["date"])
        rrf_scores[cid] *= tier_w * rec_w

    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: -rrf_scores[cid])[:top_k]

    results = []
    mode_label = "hybrid" if sem_results else "keyword-fallback"
    for cid in sorted_ids:
        item = dict(chunk_map[cid])
        item["score"] = rrf_scores[cid]
        item["match_type"] = mode_label
        results.append(item)

    return results


def format_match_snippet(
    content: str, start_line: int, query: str, max_lines: int = 12
) -> str:
    """Extract a line-numbered snippet centered around the best query token match."""
    lines = content.splitlines()
    tokens = [
        t.lower()
        for t in re.sub(r"[^\w\s]", " ", query).split()
        if len(t) >= 2
    ]

    best_idx = 0
    best_hits = -1
    for idx, line in enumerate(lines):
        low = line.lower()
        hits = sum(1 for t in tokens if t in low)
        if hits > best_hits:
            best_hits = hits
            best_idx = idx

    half = max_lines // 2
    win_start = max(0, best_idx - half)
    win_end = min(len(lines), win_start + max_lines)
    win_start = max(0, win_end - max_lines)

    numbered = [
        f"{start_line + i:4d}: {lines[i]}" for i in range(win_start, win_end)
    ]
    if win_start > 0:
        numbered.insert(0, "   ...")
    if win_end < len(lines):
        numbered.append("   ...")
    return "\n".join(numbered)


# ---------------------------------------------------------------------------
# Multi-Harness Transcript Ingestion
# ---------------------------------------------------------------------------


def parse_transcript_jsonl(transcript_path: Path) -> tuple[str, str] | None:
    """Convert OpenAI/Anthropic/Claude-Code/Gemini JSONL logs into clean markdown."""
    try:
        raw_lines = transcript_path.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in raw_lines if line.strip()]
    except Exception:
        return None

    mtime = transcript_path.stat().st_mtime
    date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    conv_id = (
        transcript_path.stem
        if transcript_path.stem != "transcript"
        else transcript_path.parents[2].name
    )

    turns: list[dict[str, str]] = []
    curr_user = ""
    curr_agent: list[str] = []

    for rec in records:
        # Format A: Gemini step format
        stype = rec.get("type")
        source = rec.get("source")
        if stype in ("USER_INPUT", "PLANNER_RESPONSE"):
            content = str(rec.get("content", ""))
            if stype == "USER_INPUT" and source == "USER_EXPLICIT":
                if curr_user and curr_agent:
                    turns.append({"user": curr_user, "agent": "\n\n".join(curr_agent).strip()})
                cleaned = re.sub(
                    r"<USER_REQUEST>(.*?)</USER_REQUEST>", r"\1", content, flags=re.DOTALL
                )
                cleaned = re.sub(r"<ADDITIONAL_METADATA>.*", "", cleaned, flags=re.DOTALL).strip()
                curr_user = cleaned
                curr_agent = []
            elif stype == "PLANNER_RESPONSE" and source == "MODEL" and content.strip():
                curr_agent.append(content.strip())
            continue

        # Format B: Standard role/content or Claude Code message format
        msg = rec.get("message", rec) if isinstance(rec.get("message"), dict) else rec
        role = msg.get("role") or rec.get("role")
        raw_content = msg.get("content", "")
        if isinstance(raw_content, list):
            text_parts = [
                p.get("text", "")
                for p in raw_content
                if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text")
            ]
            text = "\n".join(t for t in text_parts if t).strip()
        else:
            text = str(raw_content).strip()

        if not text:
            continue

        if role == "user":
            if curr_user and curr_agent:
                turns.append({"user": curr_user, "agent": "\n\n".join(curr_agent).strip()})
            curr_user = text
            curr_agent = []
        elif role in ("assistant", "model"):
            curr_agent.append(text)

    if curr_user and curr_agent:
        turns.append({"user": curr_user, "agent": "\n\n".join(curr_agent).strip()})

    if not turns:
        return None

    first_topic = re.sub(r"^activate\s+\w+\s*", "", turns[0]["user"], flags=re.I).strip()
    if not first_topic and len(turns) > 1:
        first_topic = turns[1]["user"].strip()
    if not first_topic:
        first_topic = "session"

    slug = slugify(first_topic)
    filename = f"{date_str}-{conv_id[:8]}-{slug}.md"
    title = first_topic[:80].replace("\n", " ")

    md_lines = [
        f"# Session Transcript: {title}",
        "",
        f"- **Date**: {date_str}",
        f"- **Conversation ID**: `{conv_id}`",
        f"- **Turns**: {len(turns)}",
        "",
        "---",
        "",
    ]

    for i, t in enumerate(turns, 1):
        user_summary = t["user"][:60].replace("\n", " ").strip()
        md_lines.append(f"## Turn {i}: {user_summary}")
        md_lines.append("")
        md_lines.append("### Rachel")
        md_lines.append(t["user"])
        md_lines.append("")
        md_lines.append("### Agent")
        md_lines.append(t["agent"])
        md_lines.append("")

    return filename, "\n".join(md_lines)


def sync_transcripts(source_dir: Path, days: int | None = None, limit: int | None = None) -> list[str]:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if not source_dir.exists():
        return []

    candidates = list(source_dir.rglob("*.jsonl"))
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if days is not None:
        cutoff = time.time() - (days * 86400)
        candidates = [p for p in candidates if p.stat().st_mtime >= cutoff]
    if limit is not None:
        candidates = candidates[:limit]

    synced: list[str] = []
    for p in candidates:
        res = parse_transcript_jsonl(p)
        if not res:
            continue
        fname, content = res
        target = TRANSCRIPTS_DIR / fname
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            target.write_text(content, encoding="utf-8")
            synced.append(fname)

    return synced


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Portable Living Memory & Hybrid Search Engine"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # wake
    p_wake = subparsers.add_parser(
        "wake",
        help="Execute the Phase 3 cutoff: print WAKE.md, MEMORY.md (if present), and the latest diary entry",
    )
    p_wake.add_argument(
        "--sync-days",
        type=int,
        default=3,
        help="Optionally sync transcripts modified in the last N days during wake",
    )

    # index
    p_index = subparsers.add_parser(
        "index", help="Incrementally index notes/, docs/, transcripts/, and MEMORY.md"
    )
    p_index.add_argument("--force", action="store_true", help="Rebuild index from scratch")
    p_index.add_argument(
        "--backfill-embeddings",
        action="store_true",
        help="Populate missing vector embeddings for chunks indexed while offline",
    )
    p_index.add_argument("--quiet", action="store_true", help="Suppress per-file progress")

    # search
    p_search = subparsers.add_parser(
        "search", help="Query memory via hybrid (RRF), semantic, or keyword (BM25) search"
    )
    p_search.add_argument("query", type=str, help="Search query")
    p_search.add_argument(
        "--mode",
        choices=["hybrid", "semantic", "keyword"],
        default="hybrid",
        help="Search mode (default: hybrid with automatic keyword fallback)",
    )
    p_search.add_argument(
        "--type",
        choices=["all", "pinned", "note", "doc", "transcript"],
        default="all",
        help="Filter by document tier",
    )
    p_search.add_argument("--top-k", type=int, default=5, help="Max results to return")
    p_search.add_argument("--json", action="store_true", help="Output raw JSON")

    # sync-transcripts
    p_sync = subparsers.add_parser(
        "sync-transcripts", help="Ingest JSONL conversation logs from a harness directory"
    )
    p_sync.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ.get("TRANSCRIPT_SOURCE_DIR", "")),
        help="Root directory containing .jsonl logs (or set TRANSCRIPT_SOURCE_DIR)",
    )
    p_sync.add_argument("--days", type=int, default=3, help="Only sync logs from last N days")
    p_sync.add_argument("--limit", type=int, default=None, help="Max logs to process")

    # stats
    subparsers.add_parser("stats", help="Show memory index statistics and active provider")

    args = parser.parse_args()

    if args.command == "wake":
        if WAKE_FILE.exists():
            print(WAKE_FILE.read_text(encoding="utf-8").rstrip())
        if MEMORY_FILE.exists():
            print("\n--- PINNED MEMORY (MEMORY.md) ---")
            print(MEMORY_FILE.read_text(encoding="utf-8").rstrip())
        if NOTES_DIR.exists():
            notes = sorted(NOTES_DIR.glob("*.md"))
            if notes:
                latest = notes[-1]
                print(f"\n--- LATEST DIARY ({latest.relative_to(AGENT_ROOT).as_posix()}) ---")
                print(latest.read_text(encoding="utf-8").rstrip())
        index_files(force=False, verbose=False)

    elif args.command == "index":
        res = index_files(
            force=args.force,
            backfill_embeddings=args.backfill_embeddings,
            verbose=not args.quiet,
        )
        print(
            f"Status: {res['status']} | Provider: {res['provider']} | "
            f"Updated: {res['updated_files']} | Deleted: {res['deleted_files']} | "
            f"New chunks: {res['new_chunks']} | Backfilled: {res['backfilled_embeddings']} | "
            f"Total chunks: {res['total_chunks']}"
        )

    elif args.command == "sync-transcripts":
        if not str(args.source):
            print("No transcript source directory specified (use --source or TRANSCRIPT_SOURCE_DIR).")
            return
        synced = sync_transcripts(args.source, days=args.days, limit=args.limit)
        print(f"Synced {len(synced)} transcript(s) to {TRANSCRIPTS_DIR}")
        for f in synced:
            print(f"  + {f}")
        if synced:
            res = index_files(force=False, verbose=False)
            print(f"Indexed {res['new_chunks']} new chunks (total: {res['total_chunks']}).")

    elif args.command == "stats":
        con = get_db_connection()
        init_db(con)
        files_c = con.execute("SELECT COUNT(*) as c FROM indexed_files").fetchone()["c"]
        chunks_c = con.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        emb_c = con.execute(
            "SELECT COUNT(*) as c FROM chunks WHERE embedding IS NOT NULL"
        ).fetchone()["c"]
        by_type = {
            row["doc_type"]: row["c"]
            for row in con.execute(
                "SELECT doc_type, COUNT(*) as c FROM chunks GROUP BY doc_type"
            ).fetchall()
        }
        con.close()
        print(f"Agent Root:        {AGENT_ROOT}")
        print(f"Database Path:     {DB_PATH}")
        print(f"Embed Provider:    {detect_embed_provider()}")
        print(f"Indexed Files:     {files_c}")
        print(f"Total Chunks:      {chunks_c} ({emb_c} with dense vectors)")
        print(f"Breakdown by Tier: {json.dumps(by_type)}")

    elif args.command == "search":
        index_files(force=False, verbose=False)
        con = get_db_connection()
        init_db(con)
        if args.mode == "hybrid":
            hits = hybrid_search(con, args.query, top_k=args.top_k, doc_type=args.type)
        elif args.mode == "semantic":
            hits = semantic_search(con, args.query, top_k=args.top_k, doc_type=args.type)
        else:
            hits = keyword_search(con, args.query, top_k=args.top_k, doc_type=args.type)
        con.close()

        if args.json:
            print(json.dumps(hits, indent=2))
            return

        if not hits:
            print(f"No results found for query: '{args.query}'")
            return

        actual_mode = hits[0]["match_type"]
        print(f"Found {len(hits)} result(s) for '{args.query}' (mode: {actual_mode}):\n")
        for i, h in enumerate(hits, 1):
            link = f"[{h['rel_path']}#L{h['start_line']}-L{h['end_line']}](file://{h['file_path']}#L{h['start_line']}-L{h['end_line']})"
            print(f"### {i}. {link}")
            print(
                f"**Date:** {h['date']} | **Tier:** {h['doc_type']} | "
                f"**Section:** {h['section_title']} | **Score:** {h['score']:.4f}"
            )
            snippet = format_match_snippet(h["content"], h["start_line"], args.query)
            print(f"```text\n{snippet}\n```\n")


if __name__ == "__main__":
    main()
