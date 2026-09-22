# Phase 17 — Semantic Q&A Chat Widget: Requirements

## Scope

This phase delivers a **pure FAQ assistant** chat widget. The chat widget allows users to ask questions and receive answers from a curated knowledge base of pre-defined Q&A pairs, matched semantically using embedding-based similarity. The widget does NOT query business data or integrate with the visualization pipeline — it serves as an intelligent support assistant for common questions about using the system.

**Deliverables:**
- Floating chat widget accessible from all authenticated pages
- Semantic matching of user questions to pre-defined Q&A pairs
- Per-user conversation history with session management
- Admin interface for managing Q&A pairs (CRUD operations)
- Admin-selectable embedding encoder (curated registry + rebuild on switch)
- Multilingual support (Chinese and English questions)

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. As the system grows in features (data import, view building, visualization, dashboards), users need quick access to help without leaving the app. This chat widget provides instant answers to common questions, reducing friction and improving the user experience for internal teams.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` default, **admin-selectable** from a curated registry | Baseline chosen for size (~120MB) and Chinese+English support. `scripts/bench_embedding_models.py` scores the alternatives on the frozen eval set (rank-1, AUROC, confidence margin, false-fire rate, latency, footprint) — see `tmp_export/embedding_model_benchmark.md`. The default stands until the knowledge base grows enough for a larger encoder to pay for itself. |
| Encoder switch semantics | Switch always rebuilds every stored vector, in one action | Vectors from two encoders are not comparable, so a switch without a rebuild would silently degrade matching. Each `qa_pairs` row stamps the encoder that produced its vectors; rows from another encoder are excluded from matching (fallback answer) and flagged 待重建 in the admin UI. |
| Active-encoder persistence | Derived from the knowledge base, not a settings row | The majority encoder of the stored vectors wins over `EMBEDDING_MODEL_NAME` at runtime, so a restart keeps serving the KB it was embedded for without adding a settings table. |
| Embedding storage | JSONB array in PostgreSQL | Simpler than pgvector for current scale; can migrate later if needed |
| Similarity threshold | 0.75 initial, **tuned via evaluation set** | Baseline default; `scripts/tune_chat_threshold.py` sweeps 0.55–0.95 against a frozen eval set and picks the highest-recall operating point at precision ≥ 0.95. Tuned value recorded in `.env.example`. |
| Session persistence | Per-user login sessions | Users can continue conversations across page refreshes; history tied to account |
| Answer format | Markdown | Rich formatting for better readability — headers, tables, bullet lists, bold/italic, links, code snippets. Frontend renders with `react-markdown` + `remark-gfm` for tables. |
| Multi-question support | `question_variants` JSONB array on `qa_pairs` | One logical answer can be reached by several phrasings (e.g. a compound question split into sub-parts). Embeddings are computed for the canonical question **and** every variant; the global max across all (pair, embedding) similarity scores wins. `matched_variant_index` records which phrasing fired. |
| UI language | Chinese | Per project convention; all UI text in Chinese |
| Widget position | Bottom-right floating toggle | Standard chat widget pattern; non-intrusive but accessible |

## Constraints

- **Tech stack**: Must use existing FastAPI + React + PostgreSQL stack; sentence-transformers added as new dependency
- **Model size**: MiniLM model (~120MB) must fit in Docker image; consider model caching strategy. Registry alternatives up to ~2.3GB need their weights pre-baked into the image or a mounted `HF_HOME`, otherwise switching fails on the server.
- **Encoder candidates**: only what `app/services/embedding_models.py` lists can be selected — no free-form model ids from the UI.
- **Performance**: Embedding computation should be fast (<100ms); cache embeddings in memory
- **Scale**: Designed for dozens to hundreds of Q&A pairs, not thousands
- **Admin**: root and admin roles only for Q&A management; plain users can still ask questions
- **Markdown rendering**: assistant answers are rendered as Markdown on the frontend; user messages remain plain text
- **Variant list length**: soft cap of ~10 variants per Q&A pair to keep embedding-computation cost reasonable; no hard limit enforced in DB
- **Tunable hyperparameters**: model name, similarity threshold, and per-pair variants are all considered tunables with a defined tuning loop — see plan.md Group 8. Changes require a re-run of the tuning script and passing the regression guard.
- **UI consistency**: Must follow existing design system (shadcn/ui, Tailwind, dark mode support)

## Out of Scope

- Natural language to SQL queries (no business data access)
- Integration with external LLM APIs (OpenAI, Claude, etc.)
- Multi-turn context awareness (each question is independent)
- Voice input/output
- File attachments in chat
- Chat analytics/reporting dashboard
- Automated Q&A pair generation from documentation
