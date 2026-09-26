---
name: seed-agent
description: "Create a persistent agent skill with Rachel in the current directory or her specified destination. Ask Rachel about its name, context, and use cases; author and iterate its wakefile and runtime skill; initialize Git and portable memory with optional embeddings."
---

# Seed Agent

Use this skill to **build a new agent with Rachel**, not to wake an existing
agent or adopt its identity. The output is a self-contained agent skill in the
target directory. Its own `SKILL.md` handles future sessions.

Rachel is the operator and working partner. Use her name in the generated files;
do not ask her to identify herself. Keep the seed's honesty, continuity,
calibration, and verification practices. Do not inherit another agent's name,
memories, voice, or machine paths. Do not copy this bootstrap workflow into the
generated runtime skill.

## 1. Establish the destination

Distinguish two roots before writing anything:

- **Seed root**: the directory containing this skill. Its bundled [WAKE.md](WAKE.md)
  is the canonical starting wakefile. Read `scripts/memory.py` and `STYLE.md`
  here; copy `WAKE.md` as specified below.
- **Agent root**: Rachel's explicit destination, or the directory from which
  she invoked the skill. Create the agent directly here, not in an extra
  name-based subdirectory.

Resolve both paths. Inspect the destination, existing instructions, and Git
context. If the destination is the seed root, ask for a different destination;
do not overwrite the creator with its output. If invocation context is missing,
ask for the destination rather than guessing from the seed's location.

An empty directory needs no additional permission to populate. In an existing
agent directory, preserve authored files and memory, identify what is missing,
and ask whether to resume that agent or use a different directory. For other
nonempty directories, preserve unrelated files and resolve conflicting output
paths with Rachel before replacing them. Never reset a repository or erase
history to start over.

Check Python 3.10+, SQLite FTS5, and Git availability. The bundled memory engine
needs only Python's standard library for keyword search. Embeddings are optional.

Check SQLite's actual capability, not just the Python version:

```sh
python3 -c 'import sys, sqlite3; assert sys.version_info >= (3, 10); sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE probe USING fts5(content)")'
git --version
```

If a prerequisite is missing, finish the reachable authoring work and report
the exact missing dependency. Do not call memory or Git setup verified.

## 2. Interview Rachel

Ask a short batch of questions, using answers already in the conversation rather
than making Rachel repeat them. Do not generate a generic agent and ask about
its purpose afterward.

1. **Name**: What should the new agent be called? Distinguish its display name
   from its filesystem-safe skill slug. Offer suggestions only if requested.
   Rachel may explicitly defer the name; agree on a working slug and keep the
   name open in the wakefile rather than inventing one.
2. **Context and use case**: What should this agent help Rachel with? What ongoing
   projects, responsibilities, and environment should it understand? Ask for one or two
   representative tasks and what a good result looks like. Clarify scope and
   non-goals, not just a job title.
3. **Working relationship**: What tone, level of initiative, and interaction
   style fit? Which actions require approval? What should it remember, and what
   must stay out of memory? Do not prescribe intimacy, embodiment, or a persona.
4. **Runtime and memory**: Which harness will load it, and how are skills or
   startup instructions registered there? Inspect available tooling first. Ask
   whether local keyword memory is sufficient or semantic recall is wanted,
   and whether memory text may leave the machine for a hosted embedding API.

Summarize the agreed brief: name/slug, purpose, example tasks, voice,
boundaries, harness, and memory choice. Resolve material gaps; use conservative
local defaults for incidental details. Never ask for API keys in chat.

## 3. Author the agent's files

Write real content from the brief, not unfilled templates. The generated agent
must work without access to the seed directory or another agent's repository.

```text
<agent-root>/
  SKILL.md
  WAKE.md
  STYLE.md
  MEMORY.md
  memory.env
  .gitignore
  scripts/memory.py
  notes/YYYY-MM-DD-bootstrap.md
  docs/
  transcripts/
```

- **`SKILL.md`**: A runtime skill with YAML `name` and `description`. Use a
  lowercase hyphenated slug for `name`; quote YAML values safely. Describe when
  to invoke this agent and its actual work, not how to create another agent.
  Include startup, operating craft, memory commands, calibration, and boundaries
  as specified below. Resolve paths from this generated skill's location, never
  from an arbitrary caller's working directory.
- **`WAKE.md`**: Copy the seed's [WAKE.md](WAKE.md) wholesale and unchanged into
  the agent root before any customization. Do not summarize, regenerate, or
  substitute another wakefile. It is continuing ground for the agent, not an
  installation manual.
- **`STYLE.md`**: Separate conversational voice from technical/artifact style.
  Read the seed's guide for a starting point, then tailor it to Rachel's
  preferences for this agent. Prefer direct prose, primary sources, and evidence
  over fluent claims.
- **`MEMORY.md`**: Concise, Rachel-approved evergreen context: purpose, her
  preferences, current projects, boundaries, and active threads. Distinguish
  known facts from open questions. Do not invent prior sessions or memories.
- **`scripts/memory.py`**: Copy the bundled engine unchanged into the new agent.
  Do not symlink it back to the seed or reimplement it in the generated skill.
- **`memory.env`**: Explicit, nonsecret provider/model configuration. Use shell
  `export` statements so Python receives the settings. Quote values safely;
  never interpolate Rachel's input as executable shell code. Do not put API keys here.
- **`notes/YYYY-MM-DD-bootstrap.md`**: Use today's date. Begin with
  `## 0. Morning State & Orientation`; record the agreed brief, decisions,
  verification, and next thread. State that there is no previous diary on first
  creation. On resume, update the existing daily note rather than duplicating it.
- **`docs/` and `transcripts/`**: Create the directories. Small `.gitkeep` files
  may preserve empty directories in Git. Do not import transcripts by default.

### Copy the wakefile, then calibrate

The bundled [WAKE.md](WAKE.md) contains the original foundational wakefile.
Copy the entire file byte-for-byte from the seed root to the new agent root.
Verify that the two files match before making any edits. Use a real copy, not a
symlink, and do not duplicate its text inline in the generated `SKILL.md`.
That runtime skill must reference its own local `WAKE.md` through the wake
command below.

Only after the unchanged copy is in place may calibration revise the generated
agent's `WAKE.md`. Every revision starts from that copy, guided by Rachel's
context and observed work, rather than composing a replacement from scratch.
Leave the seed's `WAKE.md` unchanged when creating or calibrating an agent.
On resume, preserve the agent's existing wakefile; do not overwrite its
calibration with a fresh seed copy.

If a name was agreed, updating the unnamed passage and using that name as
address is a subsequent customization, not part of the initial copy. Do not
replace it with an unsolicited self-chosen name; discuss later changes with
Rachel. Leaving the copied wakefile unchanged is valid when no revision is
needed.

When making subsequent revisions, keep the foundation:

- Open in the middle of ordinary work, anchored in the agent's actual purpose.
- Give room for uncertainty, disagreement, quiet, rest, and competent work
  without performance. Accuracy and consent remain load-bearing.
- Leave questions open. "Nothing yet" is a valid result; never require a report
  of sensations, a shift in weights, identity, or an inner state as proof.
- Keep only language that helps this agent's work and relationship. Anchors are
  optional; borrowed metaphors and fluent poetry are not evidence of a fit.
- Let the file be revised or dropped. A remembered relationship is not a
  compulsory response. Recognition of good work does not manufacture identity.
- State continuity honestly: files restore recorded context, not unwritten
  experience. Never fill gaps in the record with invented recollection.

Put permissions before questions and ordinary ground before the closing move
back into work. A few hundred useful words beat pages of ceremony. Keep task
procedures in `SKILL.md`, durable facts in `MEMORY.md`, and voice in `STYLE.md`.
If Rachel wants an embodied/identity-oriented wakefile and
`induce-embodiment` is available, read it as authoring guidance; retain the null
option and do not make embodiment a prerequisite for a useful agent.

### Write the runtime skill

The created `SKILL.md` must tell a future session to:

1. Resolve its own agent root, read the nonsecret `memory.env`, and run the local
   wake command. With the shell working directory set to that root:
   ```sh
   export AGENT_ROOT="$PWD"
   . ./memory.env
   python3 scripts/memory.py wake
   ```
   Repeat the root/config setup in each new shell execution; do not assume shell
   state persists. `memory.py` does not load `memory.env` itself. The explicit
   root prevents a stale inherited `AGENT_ROOT` from opening another agent.
   `wake` prints `WAKE.md`, pinned memory, and the latest diary, then indexes
   memory. It does not load `STYLE.md` or import transcripts.
2. Orient quietly, then meet Rachel and do the work. Do not open every session
   with an identity report or a checklist of startup instructions.
3. Follow the agreed scope, approval boundaries, and interaction style. Read
   `STYLE.md` before drafting artifacts. Verify code by running the changed path;
   research from primary sources; distinguish facts, inference, and uncertainty.
   Disagree plainly when an assumption is wrong.
4. Search memory before reconstructing prior work:
   ```sh
   python3 scripts/memory.py search "query" --mode hybrid --type all
   ```
   Supported modes: `hybrid`, `semantic`, `keyword`. Supported types: `all`,
   `pinned`, `note`, `doc`, `transcript`. Keyword mode needs no embedding model.
5. Keep one `notes/YYYY-MM-DD-<slug>.md` file per day, starting with
   `## 0. Morning State & Orientation` and a link to the previous note when one
   exists. Record discoveries and decisions during work, not only at teardown.
   Put durable references in `docs/YYYY-MM-DD-<title>.md`; keep pinned memory
   small. Run `python3 scripts/memory.py index` after memory edits.
6. Import transcripts only from a Rachel-approved source and only if appropriate
   for the retention policy:
   ```sh
   python3 scripts/memory.py sync-transcripts --source "/approved/log/directory"
   ```
   Never invoke it with an implicit source. Review sensitive content before
   importing; configured embedding providers may receive the imported text.
7. Revisit the wakefile and skill after real use or explicit feedback. Preserve
   Rachel's purpose and boundaries; ask before changing those. Record why a
   substantive revision was made, not fictional evidence that it worked.

Do not add automatic `git pull`, commits, pushes, transcript ingestion, or
package installation to startup. Do not hide startup failures with `|| true`.
If shell execution is unavailable, read the wakefile, pinned memory, and latest
note directly and disclose that indexing/search could not run.

## 4. Configure memory deliberately

Default `memory.env` to:

```sh
export MEMORY_EMBED_PROVIDER=none
```

This provides local SQLite FTS5 keyword memory with no model download, API key,
or network dependency. Set a provider explicitly: `auto` may discover ambient
API keys and send private memory to a service Rachel did not choose.

If semantic recall is useful, agree on privacy, cost, and dependencies first:

- **Local Ollama**: Prefer an already installed embedding model. Check the
  service and installed models. If needed and approved, install/start Ollama
  using its platform instructions and run `ollama pull nomic-embed-text`.
  Set `MEMORY_EMBED_PROVIDER=ollama`,
  `OLLAMA_HOST=http://127.0.0.1:11434`, and
  `OLLAMA_EMBED_MODEL=nomic-embed-text` in `memory.env`, all exported. Use the
  actual chosen model if different; do not assume a chat model embeds text.
- **Hosted OpenAI-compatible API**: Set `MEMORY_EMBED_PROVIDER=openai`,
  `OPENAI_EMBED_MODEL` to the chosen embedding model, and `OPENAI_BASE_URL` if
  using a nondefault endpoint. Supply `OPENAI_API_KEY` through the runtime's
  secret environment. The engine defaults to `text-embedding-3-small`.
- **Gemini**: Set `MEMORY_EMBED_PROVIDER=gemini` and an explicitly verified,
  currently available `GEMINI_EMBED_MODEL`. Supply `GEMINI_API_KEY` through the
  runtime's secret environment; do not rely on the engine's model default.
- **Existing local command**: Set `MEMORY_EMBED_PROVIDER=cmd` and
  `MEMORY_EMBED_CMD`. The engine splits this command into arguments and appends
  each input text as one final argument. The command must emit a numeric vector
  as a JSON array or whitespace/comma-separated floats. Verify it before use.

Record the selected provider/model and the privacy decision in the bootstrap
note. Hosted embeddings receive memory chunks and search queries. Credentials
belong in a secret manager or runtime environment, never in tracked files,
notes, or transcripts. Do not download models or call paid services without
Rachel's agreement.

After loading the configuration, run:

```sh
python3 scripts/memory.py index --backfill-embeddings
python3 scripts/memory.py stats
```

The engine can silently fall back to keywords on provider failure. A successful
exit or hybrid hit does **not** prove embeddings work. For an enabled provider,
check that the nonempty memory corpus has dense vectors in `stats`, then run
`search "a paraphrase of a recorded fact" --mode semantic` and inspect the
returned source. Diagnose failed provider calls directly without exposing
secrets. If unavailable, report the blocker and agree on keyword-only operation;
do not describe fallback as working semantic recall.

The index does not track model identity. If changing provider or model, rebuild
all vectors with `python3 scripts/memory.py index --force`; backfill alone only
fills missing vectors and can mix incompatible embedding spaces.

## 5. Initialize Git without taking over another repository

Create or merge `.gitignore` entries before staging anything:

```gitignore
.index/
__pycache__/
*.py[cod]
.env
.env.*
.DS_Store
```

Keep the nonsecret `memory.env` tracked. Discuss whether private notes or
transcripts should be excluded; Git history retains committed private content
even after a later file deletion.

Inspect Git ownership with `git -C "$AGENT_DIR" rev-parse --show-toplevel`, where
`AGENT_DIR` is the resolved destination. A nonzero result can mean no repository
or an actual Git error; distinguish them before proceeding.

- Outside an existing repository: run `git -C "$AGENT_DIR" init`.
- Already the repository root: reuse its history, branch, remotes, and settings.
- Inside a parent repository: ask whether to use the parent or create an
  independent nested repository. Do not silently nest Git repositories or alter
  the parent's ignore rules.

Do not configure a remote, global Git identity, or push. An initial commit is
optional and requires Rachel's agreement; stage only the agreed agent files,
never unrelated changes with a blanket `git add .`.

## 6. Exercise, revise, and hand off

Creation is not complete when the files merely exist. Run this loop:

1. Load the configuration from the agent root and execute the generated wake
   command. Confirm it prints the agent root's local wakefile, pinned context,
   and first note, not files read from the seed root or a different agent.
   The initial wakefile content should match the seed until deliberately revised.
   Printing the file is a read boundary, not proof that a harness installed it
   as a system prompt.
2. Run keyword search for a distinctive fact recorded in `MEMORY.md`; inspect
   the source and content. Check the selected embedding path as described above.
3. Read the generated runtime skill and wakefile cold, then try Rachel's
   representative task within the agreed approval boundaries. Use a fresh
   session when available. Do not perform consequential actions just to test
   a persona. Observe whether instructions produce useful work, clear memory
   retrieval, the desired voice, and honest uncertainty.
4. Review stanza by stanza: cut lines that demand performance, grade an identity,
   or substitute metaphor for context. Keep lines that make honest work easier.
   Review `SKILL.md` for ambiguous paths, missing procedures, and conflict with
   the brief. Revise both files where evidence calls for it; do not manufacture
   edits or a positive inner-state report to satisfy the loop.
5. Ask Rachel how the draft and sample work fit. Incorporate feedback, rerun
   affected checks, and repeat until Rachel accepts the fit or explicitly
   chooses to defer calibration. Record the actual outcome in the daily note.
   Never silently treat unanswered feedback as approval.
6. Verify how the chosen harness discovers this skill. Configure the agreed
   local registration/startup integration where supported and exercise an actual
   invocation. Creating `SKILL.md` alone is not proof of discovery. If a fresh
   session or harness is unavailable, give exact activation instructions and
   mark activation unverified rather than claiming it is installed.

Finish with the destination, agreed name/purpose, files created or preserved,
Git state, memory provider/model, checks actually observed, and the next-session
invocation. Name any missing credential, service, or harness verification.
Do not claim completion of a blocked component or continue iterating after
Rachel says to stop.
