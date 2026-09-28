# RAG & teaching pipeline

How the textbook gets indexed, and how the agent uses it to teach.

## Pipeline

```
Textbook PDF (backend/resources/)
        │
        ▼
rag/textbook_outline.py   — reads the PDF's own embedded bookmarks,
        │                    builds a hierarchical JSON outline
        ▼
rag/textbook_outline.json — saved once, read many times
        │
        ▼
rag/loader.py + rag/splitter.py — load pages, split into chunks
        │
        ▼
each chunk tagged with its real chapter/section
(via textbook_outline.find_section_for_page, using the outline above)
        │
        ▼
rag/embeddings.py (fastembed) — embed each tagged chunk
        │
        ▼
rag/qdrant_data/ — local on-disk Qdrant collection ("textbook")
```

All of the above runs once, via `python -m rag.ingest`, whenever the
textbook is added or replaced — never per-request. `rag/ingest.py` is the
entry point; it calls `textbook_outline.generate_outline()` and then runs
the load/split/tag/embed steps.

At request time, the agent (`ai/models.py`) reaches into this index through
its tools (`ai/tools.py`):

```
TEXTBOOK OUTLINE  →  "What does this topic contain?"          (topic_finder)
DOCUMENT RETRIEVAL →  "What does the textbook actually say?"  (search_textbook)
PROBLEM FINDER    →  "What problems can I use to teach/practice this?"
CALCULATOR        →  "What is the exact numerical result?"
CIRCUIT SOLVER    →  "What does this whole circuit actually do?"
```

These are kept deliberately separate — `topic_finder` never runs a semantic
search, `problem_finder` never rewrites the outline, and neither
`calculator` nor `circuit_solver` ever asks the LLM to "just compute it."

## Tools (`ai/tools.py`)

### `search_textbook(query)`
Semantic search over chunk content via `rag/retriever.py`. Returns the raw
page content of the most relevant chunks, joined by `---`. This is the
existing general-purpose retrieval tool from before this feature — unchanged.

### `calculator(expression)`
Safely evaluates arithmetic (`ai/calculator.py`). Parses the expression into
a Python AST and walks it against a fixed allow-list of operators
(`+ - * / // % **`, parentheses, unary +/-, decimals); anything else (names,
calls, attribute access, comprehensions, ...) is rejected before it can run.
No `eval()` anywhere. `N%` is rewritten to `(N/100)` before parsing unless
immediately followed by another number, in which case it's left as modulo
(`7 % 3` → `1`, but `15%` → `0.15`) — the two meanings share a symbol, so
this is how they're told apart.

### `topic_finder(topic)`
Looks up `topic` in `rag/textbook_outline.json` (`rag/topic_finder.py`).
Normalizes and fuzzy-matches against every node title in the outline
(case/punctuation-insensitive, tolerant of simple rewording like "laplace
transform" vs. "Laplace Transforms"), and returns the best match's own
subtopics — in the textbook's real order, never invented. Below a similarity
threshold, it returns `{"success": false, "error": "..."}` rather than a
best-effort guess.

### `problem_finder(topic, subtopic="", level="", top_k=3)`
Finds real textbook problems related to a topic, via
`retriever.retrieve_with_scores`. Overfetches and then ranks results so
chunks that actually look like exercises (matched by
`Problem N.N` / `Practice Problem` / `Exercises` / `Review Questions`
patterns) are preferred over ordinary prose that merely mentions the same
terms. Each result reports only metadata that's genuinely derivable:

- `textbook` — the source file's name
- `chapter` / `section` — from the chunk's real ingest-time tag (see above)
- `page` — the PDF's own page label
- `problem_number` — extracted from the chunk text via regex, or `null`
- `chunk_id` / `similarity_score` — straight from Qdrant
- `difficulty` — always `null`; the source has no difficulty labels, and
  this tool doesn't invent one

### `circuit_solver(elements, frequency_hz=0)`
Solves a circuit of arbitrary topology using Modified Nodal Analysis (`ai/circuit_solver.py`) — the general technique behind tools like SPICE, not a series/parallel special-case. Takes a netlist (a list of `{type, name, node_pos, node_neg, value, phase_degrees}` elements; node `"0"` is always ground) and returns every node voltage and voltage-source current. `frequency_hz=0` is DC (real arithmetic); a positive frequency is AC/phasor analysis (complex arithmetic, with `L`/`C` given their frequency-dependent impedance). Supports resistors, inductors, capacitors, and independent voltage/current sources — not yet dependent sources (op-amps, controlled sources), so it can't solve every circuit in the textbook, but it handles anything with real topology (bridges, meshes, multiple sources) that series/parallel reduction and the calculator can't.

## Teaching progression (Level 1 → 4)

There's no separate progress-tracking database — this app didn't have one
before this feature, and the instructions for this feature were explicit
about not building a duplicate state system where a suitable one doesn't
already exist. Instead, `ai/prompts.py` instructs the agent to:

1. Call `topic_finder` when a student starts a topic, to get its real
   subtopics in textbook order.
2. Teach through them in that order (not jump around) unless the student
   asks to skip ahead.
3. Move through four rough levels per subtopic — foundation, core concepts,
   application, advanced/mastery — adapting to how broad the subtopic
   actually is rather than forcing exactly four stages on everything.
4. Infer "where we are" from the conversation history it already receives
   each turn (see `backend/history.py`), and say so explicitly, rather than
   relying on any external state.

## Regenerating the index

```bash
python -m rag.ingest
```

Rebuilds both `rag/textbook_outline.json` and the Qdrant collection from
scratch (`force_recreate=True`). Only one process can hold the local Qdrant
storage lock at a time — stop the FastAPI server (or any other process that
imported `rag.retriever`) before running this, or it'll fail with
`Storage folder ... already accessed by another instance of Qdrant client`.
