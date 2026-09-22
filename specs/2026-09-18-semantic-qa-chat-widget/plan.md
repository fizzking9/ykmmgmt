# Phase 17 — Semantic Q&A Chat Widget: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Database Models & Migrations

1. Create `qa_pairs` table model with columns: `id` (UUID PK), `question` (Text, not null — canonical phrasing), `question_variants` (JSONB, default `[]` — array of alternate phrasings that should all resolve to this answer), `answer` (Text, not null — Markdown-formatted), `embeddings` (JSONB, nullable — parallel array of embedding vectors, one per question + each variant), `category` (String(100), nullable), `is_active` (Boolean, default true), `created_at`, `updated_at`
2. Create `chat_sessions` table model with columns: `id` (UUID PK), `user_id` (UUID FK to users), `created_at`, `last_active_at`
3. Create `chat_messages` table model with columns: `id` (UUID PK), `session_id` (UUID FK to chat_sessions), `role` (String(20) — 'user' or 'assistant'), `content` (Text), `matched_qa_id` (UUID FK to qa_pairs, nullable), `matched_variant_index` (Integer, nullable — which phrasing produced the match), `similarity_score` (Float, nullable), `created_at`
4. Generate Alembic migration for all three tables
5. Add models to `app/models/__init__.py`

## Group 2 — Embedding Service

1. Install `sentence-transformers` package in backend requirements
2. Create `app/services/embedding_service.py` with:
   - Lazy-loaded singleton model (`paraphrase-multilingual-MiniLM-L12-v2`)
   - `compute_embedding(text: str) -> list[float]` — returns 384-dimensional vector
   - `compute_embeddings(texts: list[str]) -> list[list[float]]` — batch compute for question + variants
   - `compute_similarity(emb1: list[float], emb2: list[float]) -> float` — cosine similarity
   - In-memory cache for Q&A embeddings (invalidated on CRUD operations)
3. Configuration via environment variables: `EMBEDDING_MODEL_NAME`, `EMBEDDING_SIMILARITY_THRESHOLD` (default 0.75)
4. Unit tests for embedding computation, batch computation, and similarity calculation

## Group 3 — Q&A Admin API

1. Create `app/routers/chat_admin.py` with admin-only endpoints (require root or admin role):
   - `GET /api/chat/qa-pairs` — list all Q&A pairs (with pagination, optional category filter, include inactive)
   - `POST /api/chat/qa-pairs` — create Q&A pair with `question`, `question_variants: list[str]`, `answer`, `category`; batch-compute embeddings for `[question, *variants]` and store in `embeddings` array (positions align: index 0 = canonical question, 1..N = variants)
   - `PUT /api/chat/qa-pairs/{id}` — update Q&A pair; recompute embeddings whenever `question` or `question_variants` change
   - `DELETE /api/chat/qa-pairs/{id}` — soft delete (set is_active=false)
   - `POST /api/chat/qa-pairs/rebuild-embeddings` — recompute all embeddings for all entries (for model upgrades)
2. Pydantic schemas: enforce `len(embeddings) == 1 + len(question_variants)` after every write
3. Integration tests for all CRUD endpoints, including variant addition/removal

## Group 4 — Chat API

1. Create `app/routers/chat.py` with authenticated endpoints:
   - `POST /api/chat/ask` — accepts `{message: string, session_id?: UUID}`, computes embedding, finds best match above threshold, stores message in session, returns `{answer, matched_question?, matched_variant_index?, similarity_score?, session_id}`
   - `POST /api/chat/sessions` — create new session, returns session_id
   - `GET /api/chat/sessions` — list current user's sessions (ordered by last_active_at desc)
   - `GET /api/chat/sessions/{id}/messages` — get session history (paginated)
   - `DELETE /api/chat/sessions/{id}` — delete session and its messages
2. Semantic matching logic: for every active Q&A pair, compute cosine similarity of the user message against **all** embeddings (canonical question + every variant); the global maximum across all (pair, embedding) combinations wins. Record `matched_variant_index` (0 = canonical question, k>=1 = the k-th variant) and store the canonical `question` in the response so the UI shows one stable label regardless of which variant matched.
3. Fallback response when no match: return friendly message with suggestion to browse categories
4. Integration tests for ask flow, session management, edge cases, and variant-based matching (each sub-question of a multi-variant entry should return the same answer)

## Group 5 — Frontend Chat Widget Components

1. Create `frontend/src/components/chat/ChatWidget.tsx` — main container with open/close state
2. Create `frontend/src/components/chat/ChatToggleButton.tsx` — floating button (fixed bottom-right, MessageCircle icon, unread badge support)
3. Create `frontend/src/components/chat/ChatPanel.tsx` — slide-in panel from right (320-400px width, full height, header with title and close button)
4. Create `frontend/src/components/chat/MessageList.tsx` — scrollable message area with user/assistant bubbles, timestamps, auto-scroll to bottom
5. Create `frontend/src/components/chat/MessageInput.tsx` — text input with send button, Enter to send, Shift+Enter for newline
6. Create `frontend/src/components/chat/SuggestedQuestions.tsx` — clickable chips for empty state
7. Create `frontend/src/hooks/useChat.ts` — TanStack Query hooks for chat API calls
8. Add ChatWidget to AppLayout (visible on all authenticated pages)

## Group 6 — Frontend Admin Q&A Management

1. Create `frontend/src/pages/QAManagementPage.tsx` — admin page with:
   - Table of Q&A pairs: question (with a `+N` badge when variants exist), answer preview, category, active toggle, created date, actions (edit/delete)
   - "新建问答" button opening create dialog
   - Category filter dropdown
   - "重建全部向量" button with confirmation
2. Create `frontend/src/components/chat/QAEditDialog.tsx` — form with:
   - 标准问题 input (Textarea)
   - 相似问法 variants — dynamic list: each row has a text input and a remove button; "添加相似问法" button appends a new row; order does not matter (server normalizes)
   - 答案 input (Textarea with Markdown hint and live preview pane)
   - 分类 input (Input with datalist for existing categories)
   - 启用 checkbox
   - 保存/取消 buttons
3. Add route `/admin/qa-pairs` (admin only)
4. Add sidebar nav item "问答管理" under admin section
5. TanStack Query hooks for admin API

## Group 7 — Styling & Polish

1. Chat panel animations: slide-in from right, fade backdrop
2. Message bubble styling: user (right-aligned, primary color), assistant (left-aligned, muted)
3. Markdown rendering for assistant answers (using existing markdown renderer or add `react-markdown`)
4. Loading states: typing indicator for pending responses, skeleton for initial load
5. Empty state: friendly message + suggested questions
6. Error state: toast notification on API errors
7. Responsive: full-width panel on mobile, fixed width on desktop
8. Dark mode support using existing theme tokens

## Group 8 — Hyperparameter Tuning & Continuous Improvement

The chat widget exposes three tunables: `EMBEDDING_MODEL_NAME`, `EMBEDDING_SIMILARITY_THRESHOLD`, and the per-pair `question_variants` list. This group defines how they are tuned and how the tuning stays honest over time.

1. **Evaluation set** (`backend/tests/data/chat_eval.jsonl`): labeled rows of `{query, expected_qa_id | null}` — positives from `tmp_export/QAexample_formatted.md` extended with paraphrases, plus hard negatives (topically close but wrong — "上周的投诉数据" vs. entry 1's "昨日", "下月经营总览" vs. entry 2's "今日", pure off-topic). Target ≥ 30 positives and ≥ 20 hard negatives before first tuning run.
2. **Tuning script** (`backend/scripts/tune_chat_threshold.py`):
   - Loads all active Q&A pairs + embeddings, runs every eval query through the matcher, captures the top-1 `(qa_id, similarity_score, variant_index)` triple
   - Sweeps the threshold from 0.55 → 0.95 in 0.01 steps; at each step computes **precision**, **recall**, **F1**, and **fallback accuracy** (correct rejects on negatives)
   - Emits `chat_tuning_report.md` with a P/R/F1 table + confusion counts per canonical question + list of every misfire (query, expected, actual, score)
   - Selects the operating point: highest recall subject to **precision ≥ 0.95** (a wrong answer is worse than a fallback). Prints the recommended `EMBEDDING_SIMILARITY_THRESHOLD` value.
3. **Model comparison hook**: script accepts `--model <name>` so the same eval set can be run against alternative encoders (e.g. `paraphrase-multilingual-mpnet-base-v2`, `BAAI/bge-m3`). Reports wall-clock embedding latency, disk footprint, and F1 delta versus the MiniLM baseline. Default stays MiniLM; upgrade is opt-in after a documented accuracy gap.
4. **Log-driven refinement loop**:
   - Every `POST /api/chat/ask` call is logged with `(query, top_match_qa_id, top_similarity, matched_variant_index, above_threshold)` — including near-threshold misses (score between threshold-0.10 and threshold)
   - Weekly admin review page (`/admin/chat-analytics`, admin-only, follow-on iteration) surfaces: top unmatched queries, near-threshold queries, queries with `similarity_score > 0.60` that still fell through
   - Tuning actions from the review: add the unmatched query as a `question_variant` on an existing pair, create a new pair, or lower/raise the threshold based on a re-run of the tuning script
5. **Regression guard**: extend Gate 2 (backend unit tests) with a `test_chat_threshold_regression.py` that runs the tuning script against the frozen eval set and fails if precision at the tuned threshold drops below 0.95 — catches model or preprocessing drift on dependency upgrades.
6. **Tunables surfaced in `.env.example`**: `EMBEDDING_MODEL_NAME`, `EMBEDDING_SIMILARITY_THRESHOLD`, `CHAT_LOG_NEAR_THRESHOLD_WINDOW` (default 0.10). Documented inline with a one-line description of what changing each value does.

## Group 9 — Testing & Validation

1. Backend: run `pytest tests/test_chat*.py` — all tests pass
2. Frontend: run `npm run test -- ChatWidget` — all tests pass
3. Type check: `npm run tsc` — no errors
4. Lint: `npm run lint` and `ruff check` — clean
5. Hyperparameter baseline: run `python scripts/tune_chat_threshold.py` against the frozen eval set — record tuned threshold and P/R/F1 in the PR description
6. Manual verification:
   - Create Q&A pairs via admin UI (including a multi-variant pair)
   - Ask matching question — verify correct answer returned
   - Ask non-matching question — verify fallback message
   - Verify session persistence across page refreshes
   - Verify Chinese and English questions match correctly

## Group 10 — Encoder Selection & Benchmark

1. `scripts/bench_embedding_models.py`: score candidate encoders on the frozen eval set, one subprocess per candidate (memory-honest), over two knowledge-base views — `full` (question + variants, i.e. production) and `canonical` (question only, which measures how far the encoder alone bridges wording)
2. Metrics per candidate: rank-1 accuracy (Wilson 95% CI), AUROC of correct-positive vs best-negative score, mean top-1 vs runner-up margin, recall at precision ≥ 0.95 / ≥ 0.90 over a widened 0.50–0.995 sweep, near-miss false-fire rate, best F1, encode latency p50/p95, parameters / dims / load time / peak RSS
3. Registry `app/services/embedding_models.py`: curated candidates (Chinese label, dims, trade-off note, optional query-side instruction), ordered best-first by the benchmark
4. `qa_pairs.embedding_model` column + migration — every write stamps the encoder that produced the row's vectors
5. `embedding_service`: runtime override (`set_active_model`), `active_query_prefix`, `encode_query` (instruction on the query side only), and dimension-safe matching (a foreign-dimension vector is skipped, never fatal)
6. `model_selection`: reconcile the runtime encoder with the majority encoder of the stored vectors, so `EMBEDDING_MODEL_NAME` is only a bootstrap default
7. Admin API: `GET /api/chat/embedding-models` (candidates, active, threshold, rebuild-pending count) and `POST /api/chat/embedding-models/activate` (switch + rebuild in one transaction)
8. Admin UI: 问答管理 vector-model picker with the pending-switch confirm dialog, the option's trade-off note, a 待重建 badge per stale row and a pending-rebuild summary
9. Report written to `tmp_export/embedding_model_benchmark.md`; the default is only changed if a candidate wins on rank-1 *and* separation, not just on size
