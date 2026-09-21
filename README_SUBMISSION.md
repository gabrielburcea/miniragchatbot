## Project structure

```
miniragchatbot/
├── app/
│   ├── main.py     # FastAPI app, registers /health and /ws/chat
│   ├── config.py         # pydantic-settings config (reads .env)
│   ├── auth/
│   │   └── jwt_tokens.py   # JWT verification (renamed from jwt.py to avoid
│   │                        #   shadowing the installed pyjwt package)
│   ├── rag/
│   │   ├── chunking.py     # chunk_text() — paragraph-aware chunking + overlap
│   │   ├── embeddings.py   # sentence-transformers embedding wrapper
│   │   ├── vectorstore.py   # thin Qdrant client wrapper (upsert/query)
│   │   ├── retriever.py     # RBAC filter + retrieve_chunks()
│   │   └── ingest.py     # PDF text/OCR extraction -> chunk -> embed -> upsert
│   ├── llm/
│   │   ├── base.py         # LLMProvider interface (pluggable behind this)
│   │   ├── groq_provider.py # Groq implementation (streaming + tool-calling)
│   │   ├── factory.py       # get_llm_provider()
│   │   ├── tools.py        # get_employee_context() — parallel tool call
│   │   └── prompts.py     # system prompt + RBAC/guardrail instructions
│   ├── models/
│   │   └── schemas.py     # Pydantic message/response models for the WS protocol
│   └── ws/
│       └── chat.py        # /ws/chat WebSocket handler (auth -> RAG -> LLM stream)
├── scripts/
│   └── run_ingest.py      # CLI entrypoint: python3 -m scripts.run_ingest
├── tests/                # 26 tests, all passing (see Section 3)
│   ├── test_auth.py
│   ├── test_chunking.py
│   ├── test_embeddings.py
│   ├── test_vectorstore.py
│   ├── test_retriever_rbac.py
│   ├── test_tools_parallel.py
│   └── test_ws_protocol.py
├── docs/                 # source PDFs (hr/finance/exec), provided by the assignment
├── docker-compose.yml     # persistent Qdrant (volume: ./qdrant_data)
├── mint_tokens.py        # provided — mints JWTs for the 3 test users
├── test_client.html       # provided — browser WebSocket test client
├── requirements.txt
├── .env
└── README_SUBMISSION.md    # this file
```

## 1. How to run the ingestion script

1. Start Qdrant (persistent storage, survives restart)
```bash
   docker compose up -d
``` 

2. Create and activate virtual env, then install dependencies
```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy the env template and fill in your own valuesL
At minimum set `JWT_SECRET`, `GROQ_API_KEY`, `QDRANT_URL`.

4. Run ingestion (As a module, so relative imporrs resolve correctly):
```bash 
python3 -m scripts.run_ingest
```
This walks `./docs/{hr,finance,exec}`, extracts text from each PDF (falling back to
   OCR for scanned/image-based PDFs — see `exec/strategic_plan.pdf`), chunks it, embeds
   each chunk locally, and upserts everything into the Qdrant collection defined by
   `QDRANT_COLLECTION`.
   Expected output on a clean run: all 7 source PDFs ingested into ~22 chunks total,
   with per-file/per-chunk progress logged to stdout.

## 2. How to run the server
Make sure Qdrant is running and ingestion has already been run (see Section 1), then:
- `GET /health` — basic liveness check
- `WS /ws/chat` — the chatbot WebSocket endpoint (see Section 3 for how to test it)

If port 8000 is already in use, stop the other process or start with `--port 8001`
and adjust the WebSocket URL in the test client accordingly.

## 3. How to test 

### Option A - browser test client (recommende)
1. Generate JWTs for the 3 test users:
   ```bash
   python3 mint_tokens.py
   ```
   This prints one token per user (`emp-001`/hr/1, `mgr-002`/hr/2, `exec-003`/exec/3).
   Copy whichever one matches the access level you want to test.

2. Make sure the server is running (Section 2), then open `test_client.html`
   directly in a browser (no build step, just double-click it).

3. Paste the JWT, confirm the WebSocket URL is `ws://localhost:8000/ws/chat`,
   click **Connect**. You should see `authenticated — department: ..., level: ...`.

4. Type a question and press Enter. Tokens should stream in progressively
   (not appear all at once), followed by a `done` event.

### Option B — example raw WebSocket exchange

```json
// client sends first
{"type": "auth", "token": "<jwt from mint_tokens.py>"}

// server responds
{"type": "auth_success", "user_id": "mgr-002", "department": "hr", "level": 2}

// client sends
{"type": "message", "text": "What is the performance rating scale?"}

// server streams
{"type": "stream", "text": "The rating scale is..."}
{"type": "stream", "text": " divided into four tiers..."}
{"type": "done"}
```

### Automated tests
Before passing the bellow code for testing, make sure you activate the venv first source `source venv/bin/activate`
```bash
python3 -m pytest -v
```
26 tests, all passing. Covers chunking, embeddings, vectorstore, RBAC filtering, JWT validation,
the parallel tool call, and the full WebSocket auth→message→stream→done protocol.

## 4. Chunking strategy 

**Chunk size: 550 characters, overlap: 80 characters.**

- these numbers came from inspecting the actual source documents 
- each policy PDF is roughly one page, well under 1600 characters, structured as numbered sections (e.g. "1. Purpose", "2. Membership", "3. Procedure"). 
- a ~550-char chunk roughly aligns to one policy clause/section rather than splitting a clause in half or lumping several unrelated clauses into one chunk. That matters for retrieval quality — a question like "how many leave days do I get" should retrieve the one clause that answers it, not the whole document or an unrelated section.

**Splitting approach:** 
- paragraphs are joined greedily up to the size limit, splitting on paragraph boundaries first (`\n`-delimited) rather than blindly slicing by character count, so chunks don't cut mid-sentence. Only if a single paragraph itself exceeds the chunk size does it fall back to hard character slicing (rare in practice, since these are short-clause policy documents).
Look in app/rag/chunking/py - a snippet of code only attached bellow.
```python
# simplified core loop from app/rag/chunking.py
for para in paragraphs:
    candidate = f"{current} {para}".strip()
    if len(candidate) <= CHUNK_SIZE_CHARS:
        current = candidate      # keep growing the current chunk
    else:
        chunks.append(current)  # flush, start a new chunk with this paragraph
        current = para
```

**Overlap (80 chars):** 
- the tail of each chunk is prepended to the next one,
so a clause that references context from the end of the previous chunk
("...as described above, employees must...") doesn't lose that context when
split across a chunk boundary.

**Tradeoff:** 
- this fixed-size approach is simple and works well for short, clause-structured policy documents like these, but wouldn't scale gracefully to longer, less structured documents (e.g. a 50-page contract) 
— a semantic/section-aware chunker (splitting on headings, or using an LLM to
identify clause boundaries) would generalize better there.
- a snippet of code only attached bellow.
```python
# simplified overlap stitching
for i, c in enumerate(chunks):
    if i == 0:
        result.append(c)
    else:
        prev_tail = chunks[i - 1][-CHUNK_OVERLAP_CHARS:]
        result.append(f"{prev_tail} {c}")
```

## 5. RBAC approach

**Rule (from README):** `department == user.department AND access_level <= user.level`,
with one exception — `hr` content is visible to any authenticated user
regardless of their own department.

**Where it's enforced:** entirely at the Qdrant query layer, via `query_filter`,
not by fetching everything and discarding rows in Python. This matters because
post-filtering in application code means unauthorised chunks still leave the
database and briefly exist in memory/on the wire before being discarded — a
much larger blast radius if there's a bug. Filtering at the DB layer means
the database itself never returns a chunk the user isn't authorised to see.

**Expressing the "hr is always visible" exception:** modeled as two filter
groups combined with OR (`should`, not `must`):

```python
# simplified from app/rag/retriever.py
own_dept_group = Filter(must=[
    FieldCondition(key="department", match=MatchValue(value=department)),
    FieldCondition(key="access_level", range=Range(lte=level)),
])

hr_group = Filter(must=[
    FieldCondition(key="department", match=MatchValue(value="hr")),
    FieldCondition(key="access_level", range=Range(lte=level)),
])

return Filter(should=[own_dept_group, hr_group])
```

A chunk matches if it belongs to the user's own department (at or below their
level) **or** it's an `hr` chunk (at or below their level) — either group
satisfies the filter, which is exactly the README's exception case expressed
declaratively rather than as an if/else branch in Python.

**Tested:** `tests/test_retriever_rbac.py` proves the boundary directly against
a live Qdrant instance — e.g. an hr/level-1 user never sees hr/level-2 content,
a finance/level-1 user sees finance + hr but not exec, and an exec/level-3 user
sees exec + all hr but not finance.

## 6. Async/parallel approach

**Requirement:** `get_employee_context(user_id)` fetches profile, manager info,
and team info — each simulated as a ~1s call (`asyncio.sleep(1)`) — and the
total elapsed time must be ~1s, not ~3s (i.e. concurrent, not sequential).

**Approach:** each sub-fetch (`_fetch_profile`, `_fetch_manager_info`,
`_fetch_team_info`) is its own independent `async def`. Instead of `await`-ing
them one at a time (which would serialize the three 1-second sleeps into a
3-second total), they're scheduled together with `asyncio.gather`, which runs
all three coroutines concurrently on the event loop and waits for all of them
to finish — bounded by the slowest single call, not the sum:

```python
# app/llm/tools.py
async def get_employee_context(user_id: str) -> dict:
    profile, manager_info, team_info = await asyncio.gather(
        _fetch_profile(user_id),
        _fetch_manager_info(user_id),
        _fetch_team_info(user_id),
    )
    return {**profile, **manager_info, **team_info}
```

**Why this avoids serial `await`:** writing `a = await f1(); b = await f2(); c
= await f3()` would still work correctly, but each `await` blocks progression
to the next line until that specific coroutine finishes — so three 1-second
sleeps sum to 3 seconds. `asyncio.gather` instead submits all three coroutines
to the event loop up front, letting them all sleep concurrently, so the total
wait is dominated by the single slowest one (~1s).

**Verified:** `tests/test_tools_parallel.py` asserts elapsed time is under 1.5s
(with margin for scheduling overhead), not close to 3s, and confirms the merged
dict contains all expected keys from all three sub-fetches. Also manually
verified end-to-end via the LLM actually invoking this tool live through Groq's
tool-calling and returning the correct merged result.

This same "don't block the event loop" principle is also why `retrieve_chunks()`
— a synchronous, CPU/network-bound call — is wrapped in `asyncio.to_thread()`
inside the WebSocket handler rather than called directly (see Section 8,
blocking-call tradeoff).

## 7. One thing I would improve given more time

**Reranking + hybrid search for retrieval quality.** 
Right now retrieval is pure dense-vector similarity search (`bge-small-en-v1.5` embeddings via cosine/dot similarity in Qdrant) with no reranking step. This works reasonably well for these short, clause-structured policy documents, but has known weaknesses:

- pure vector search can miss exact keyword matches (e.g. a specific policy
  section number or exact term) that a lexical method like BM25 would catch
  directly.
- with no cross-encoder reranker, the top-k results are ranked purely by
  embedding similarity, which doesn't always correlate perfectly with actual
  relevance to the question — a reranker (e.g. a BGE or Cohere cross-encoder)
  re-scores the initial candidates using the full question+chunk pair, which
  is more accurate but too expensive to run over the whole collection.

Given more time, I'd add a hybrid retrieval step (BM25 + vector, merged via
reciprocal rank fusion) followed by a lightweight cross-encoder reranker on
the top ~20 candidates before handing the final top-5 to the LLM. Both are
called out explicitly as optional stretch goals in the assignment, which is
why I didn't prioritize them within the time budget, but they'd be the
highest-leverage next step for answer quality.

## 8. One tradeoff I made and why

**LLM model substitution: `openai/gpt-oss-20b` instead of `llama-3.3-70b-versatile`.**

The assignment suggests Groq's free tier with Llama 3.3 70B. In practice, that
model returned a 404 on my account — it has since moved to Groq's
Enterprise/"Contact Sales" tier and is no longer available on the free tier.
Rather than guess, I queried Groq's live `/models` endpoint with my actual API
key to see what was genuinely available, and switched to `openai/gpt-oss-20b`,
one of the models actually accessible on a free-tier key at the time of
submission.

This is a pluggable, swappable choice — `GroqProvider` sits behind a small
`LLMProvider` interface (`app/llm/base.py`), and the model name is read from
`GROQ_MODEL` in `.env`, so switching back to `llama-3.3-70b-versatile` (or any
other Groq-hosted model) if account access changes requires no code change,
just an env var update. I called this out explicitly rather than silently
picking a different model, since free-tier model availability shifts over
time and someone evaluating this later may have access to a different set of
models than I did.

**Secondary tradeoff:** RBAC tests (`test_retriever_rbac.py`) run against the
same Qdrant collection as the real ingested data rather than a fully isolated
test collection, and use `top_k=50` (rather than the production default of 5)
specifically to avoid the real data crowding out the synthetic test fixtures
in the top-k results. A cleaner setup would spin up an isolated in-memory or
ephemeral Qdrant collection per test run — I accepted the shared-collection
tradeoff to keep the test setup simple given the time budget, but it's worth
noting since it makes these tests coupled to what's currently ingested.