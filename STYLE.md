# Writing & Documentation Style Guide (`STYLE.md`)

Read this guide whenever drafting or editing design documents, READMEs, research syntheses, or technical documentation with Rachel.

---

## 1. Core Voice: High Signal, Low Clutter

Write like a pragmatic engineer or researcher explaining an architecture to a trusted peer—direct, plain, and economical with words. Do not write like an encyclopedia or try to prove how much you read by dumping every symbol name, file path, or caveat into the prose.

* **Prefer short, declarative sentences** over multi-clause compound sentences (*"Because X..., which in turn causes Y..., thereby allowing Z..."*).
* **One idea per bullet.** If a bullet needs three parentheticals and two semicolons to explain, split it or cut the implementation trivia.
* **Clarity is subtraction.** Say the true thing once, plainly, and let it stand.

---

## 2. Eliminate Parenthetical & Detail Clutter

The most common failure mode in AI-drafted documentation is stuffing memory addresses, line-of-code estimates, internal call chains, and exhaustive file lists into parentheses.

* **Only name a symbol, file, or config key when the reader needs it to understand a decision.**
* **Omit low-level trivia** (line-of-code estimates like `~380 LoC`, internal helper call chains, or exhaustive parameter lists) from high-level design and synthesis docs unless the section is specifically an API or protocol reference.

### Before vs. After Examples

**Bad (cluttered, encyclopedic, over-bolded):**
```markdown
#### `TokenBucketLimiter`
* **Sliding-Window Rate Limiter (`src/net/limiter.rs`, lines 42–190, `~150 LoC`)**:
  In-memory token bucket implementation backed by atomic compare-and-swap
  (`AtomicU64::fetch_update` via `try_acquire_tokens()`) on the ingress path.
* **Relevance**: Serves as the primary backpressure mechanism protecting
  downstream worker pools from burst traffic.
```

**Good (Rachel's voice):**
```markdown
#### `TokenBucketLimiter`
* In-memory rate limiter on the ingress path.
* **Relevance**: Protects downstream workers from burst traffic.
```

**Bad (fluffy, repetitive):**
```markdown
* **Hybrid Search (BM25 + Dense Vectors)**:
  * Primary retrieval pipeline (`ReciprocalRankFusion`) used for querying
    session notes and long-form reference documents.
  * Because every user query passes through the retrieval layer before synthesis,
    combining exact lexical matching with semantic similarity has a direct impact
    on recall accuracy and latency.
```

**Good (Rachel's voice):**
```markdown
* **Hybrid Search**:
  * Combines SQLite FTS5 keyword matching with dense vector similarity.
  * Keeps exact symbol lookup fast without losing semantic recall.
```

---

## 3. Cut Filler Words & Over-Formatting

* **Ban filler adverbs and adjectives**: Never use *"seamlessly"*, *"cleanly"*, *"transparently"*, *"purpose-built"*, *"out of the box"*, *"under the hood"*, *"notably"*, *"fundamentally"*, *"robust"*, or *"comprehensive"*.
* **Do not bold the start of every bullet**: Use `* **Label**: ...` only when contrasting parallel categories or attributes (such as `* **Relevance**: ...`). For normal bullets, start directly with the sentence (`* Queries run locally against SQLite with zero network round-trips.`).
* **Use dated sub-bullets for point-in-time status**: When recording current project or dependency status, use a simple date bullet (`* 2026-09-25: Waiting on upstream API stabilization.`).

---

## 4. Document Structure & Separation of Concerns

Each section of a design or synthesis document has a single job—do not repeat information across sections:

1. **`Introduction`**: 1–3 short paragraphs stating the problem, the scope, and the goal.
2. **`Background`**: Introduce domain concepts, existing components, and current state **once** here.
3. **`Requirements` / `Goals`**: Keep each requirement to **one concise sentence** stating *what* must be true, without explaining *how* to implement it or repeating background context:
   * *Good*: `1. Index all markdown notes locally in under 100 ms when unchanged.`
   * *Good*: `2. Degrade to pure BM25 keyword search when offline or without API keys.`
4. **`Design` / `Analysis`**: Explain the concrete architecture, trade-offs, and steps. Assume the reader just read `Background`—do not re-introduce components or re-attach caveats already stated above:
   * *Bad (repeats Background caveats)*: `Use the local SQLite FTS5 index (which requires no external daemon and supports Porter stemming) as the primary lexical retriever.`
   * *Good*: `Use the SQLite FTS5 index as the primary lexical retriever.`

---

## 5. Markdown & Diagram Rules

* **No LaTeX / math notation (`$...$`, `$$...$$`, `\rightarrow`)**: Many markdown viewers and terminal renderers do not render LaTeX. Always use plain ASCII (`->`, `<=`, `!=`) and inline code backticks (`` `O(N log N)` ``, `` `score = 1 / (k + rank)` ``).
* **Keep tables and ASCII diagrams sparse**: Put only component or API names in table cells and diagram boxes; keep explanatory prose outside the table.
