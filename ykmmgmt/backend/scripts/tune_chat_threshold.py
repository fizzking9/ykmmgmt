"""Sweep the chat similarity threshold against a frozen eval set.

Loads the phase's canonical Q&A knowledge base (``tests/data/qa_kb.jsonl``) and
a labelled eval set (``tests/data/chat_eval.jsonl``), embeds everything with the
active encoder, then sweeps the threshold 0.55→0.95 reporting precision /
recall / F1 / fallback-accuracy and picking the highest-recall operating point
subject to precision ≥ 0.95. Emits a Markdown report.

Because ``find_best_match`` takes the global argmax and only *then* applies the
threshold, each query's top (pair, score) is threshold-independent — computed
once, the sweep is a cheap per-query comparison.

Usage (from backend/):
    python scripts/tune_chat_threshold.py --output chat_tuning_report.md
    python scripts/tune_chat_threshold.py --model paraphrase-multilingual-mpnet-base-v2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Make `app` importable whether run as a script or a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services import embedding_service  # noqa: E402
from app.services.embedding_service import QACacheEntry  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "tests" / "data"
KB_PATH = DATA_DIR / "qa_kb.jsonl"
EVAL_PATH = DATA_DIR / "chat_eval.jsonl"

MIN_PRECISION = 0.95


class ModelUnavailableError(RuntimeError):
    """Raised when the encoder cannot be loaded (offline / no weights cached)."""


@dataclass(frozen=True)
class TopMatch:
    query: str
    expected: str | None
    pair_id: str | None  # global argmax pair (None when no candidates)
    score: float
    latency_ms: float


@dataclass
class Metrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    fallback_accuracy: float
    tp: int
    fp: int
    fn: int
    tn: int


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_entries(kb_path: Path = KB_PATH) -> list[QACacheEntry]:
    rows = _load_jsonl(kb_path)
    entries: list[QACacheEntry] = []
    for r in rows:
        texts = [r["question"], *r.get("question_variants", [])]
        entries.append(
            QACacheEntry(
                id=r["id"],
                question=r["question"],
                category=r.get("category"),
                embeddings=embedding_service.compute_embeddings(texts),
                answer=r.get("answer", ""),
            )
        )
    return entries


def build_entries_from_db() -> list[QACacheEntry]:
    """Load active pairs (with their stored embeddings) straight from the DB.

    Each row is labelled by matching its canonical question against the KB
    fixture, so the eval set's expected ids line up with the runtime UUIDs.
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.qa_pair import QAPair

    labels = {r["question"]: r["id"] for r in _load_jsonl(KB_PATH)}

    async def _load() -> list[QACacheEntry]:
        async with async_session_factory() as session:
            rows = (
                (await session.execute(select(QAPair).where(QAPair.is_active.is_(True))))
                .scalars()
                .all()
            )
        return [
            QACacheEntry(
                id=labels.get(rw.question, str(rw.id)),
                question=rw.question,
                category=rw.category,
                embeddings=[list(v) for v in (rw.embeddings or [])],
                answer=rw.answer,
            )
            for rw in rows
        ]

    return asyncio.run(_load())


def compute_top_matches(entries: list[QACacheEntry], eval_path: Path = EVAL_PATH) -> list[TopMatch]:
    out: list[TopMatch] = []
    for r in _load_jsonl(eval_path):
        t0 = time.perf_counter()
        qe = embedding_service.compute_embedding(r["query"])
        latency = (time.perf_counter() - t0) * 1000
        best = embedding_service.peek_best_match(qe, entries)
        out.append(
            TopMatch(
                query=r["query"],
                expected=r.get("expected"),
                pair_id=best.pair_id if best else None,
                score=best.score if best else 0.0,
                latency_ms=latency,
            )
        )
    return out


def metrics_at(threshold: float, matches: list[TopMatch]) -> Metrics:
    tp = fp = fn = tn = 0
    n_negatives = sum(1 for m in matches if m.expected is None)
    for m in matches:
        accepted = m.pair_id is not None and m.score >= threshold
        if m.expected is not None:  # a positive
            if accepted and m.pair_id == m.expected:
                tp += 1
            else:
                fn += 1  # gold not correctly accepted
                if accepted:  # accepted a wrong pair → also a false positive
                    fp += 1
        else:  # a negative (expected None)
            if accepted:
                fp += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fallback_accuracy = tn / n_negatives if n_negatives else 1.0
    return Metrics(threshold, precision, recall, f1, fallback_accuracy, tp, fp, fn, tn)


def sweep(matches: list[TopMatch], lo: float = 0.55, hi: float = 0.95, step: float = 0.01) -> list[Metrics]:
    thresholds = [round(lo + i * step, 2) for i in range(int(round((hi - lo) / step)) + 1)]
    return [metrics_at(t, matches) for t in thresholds]


def choose_operating_point(rows: list[Metrics]) -> Metrics | None:
    """Highest recall subject to precision ≥ MIN_PRECISION (ties → higher threshold)."""
    eligible = [m for m in rows if m.precision >= MIN_PRECISION]
    if not eligible:
        return None
    best_recall = max(m.recall for m in eligible)
    candidates = [m for m in eligible if m.recall == best_recall]
    return max(candidates, key=lambda m: m.threshold)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


def misfires(best: Metrics, matches: list[TopMatch]) -> list[tuple[str, str, str, float]]:
    rows: list[tuple[str, str, str, float]] = []
    for m in matches:
        accepted = m.pair_id is not None and m.score >= best.threshold
        if m.expected is not None:
            if not accepted:
                rows.append((m.query, m.expected, "（未命中/回退）", m.score))
            elif m.pair_id != m.expected:
                rows.append((m.query, m.expected, m.pair_id or "—", m.score))
        elif accepted:
            rows.append((m.query, "（应为回退）", m.pair_id or "—", m.score))
    return rows


def _confusion(best: Metrics, matches: list[TopMatch]) -> dict[str, dict[str, int]]:
    grid: dict[str, dict[str, int]] = {}
    for m in matches:
        if m.expected is None or m.pair_id is None or m.score < best.threshold:
            continue
        grid.setdefault(m.expected, {}).setdefault(m.pair_id, 0)
        grid[m.expected][m.pair_id] += 1
    return grid


def write_report(
    path: Path,
    model_name: str,
    rows: list[Metrics],
    best: Metrics | None,
    matches: list[TopMatch],
) -> None:
    lines: list[str] = ["# Chat 语义匹配阈值调优报告", ""]
    lines += [f"- 向量模型：`{model_name}`", f"- 评测样本：{len(matches)} 条", ""]

    header = "| 阈值 | 精确率 | 召回率 | F1 | 回退准确率 | TP | FP | FN | TN |"
    sep = "|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines += ["## 阈值扫描", "", header, sep]
    for m in rows:
        lines.append(
            f"| {m.threshold:.2f} | {m.precision:.3f} | {m.recall:.3f} | {m.f1:.3f} | {m.fallback_accuracy:.3f} "
            f"| {m.tp} | {m.fp} | {m.fn} | {m.tn} |"
        )
    lines.append("")

    if best:
        lines += [
            "## 推荐工作点",
            "",
            f"- **YKM_CHAT_SIMILARITY_THRESHOLD = {best.threshold:.2f}**"
            f"（精确率 {best.precision:.3f} ≥ {MIN_PRECISION} 下召回率最高）",
            "",
            "## 混淆计数（按标准问题）",
            "",
        ]
        grid = _confusion(best, matches)
        for gold in sorted(grid):
            parts = ", ".join(f"→ {pred}:{cnt}" for pred, cnt in sorted(grid[gold].items()))
            lines.append(f"- {gold}: {parts}")
        lines.append("")
        lines += ["## 误判清单（推荐阈值下）", "", "| 查询 | 期望 | 实际 | 相似度 |", "|---|---|---|---:|"]
        for q, exp, act, sc in misfires(best, matches):
            lines.append(f"| {q} | {exp} | {act} | {sc:.3f} |")
        lines.append("")
    else:
        note = f"- 无法在 0.55–0.95 内找到精确率 ≥ {MIN_PRECISION} 的阈值，需补充相似问法或收紧知识库。"
        lines += ["## 推荐工作点", "", note, ""]

    lats = [m.latency_ms for m in matches]
    lines += ["## 延迟", "", f"- p50: {_percentile(lats, 50):.1f} ms", f"- p95: {_percentile(lats, 95):.1f} ms", ""]

    path.write_text("\n".join(lines), encoding="utf-8")


def run_eval(model_name: str | None = None, local_only: bool = False, from_db: bool = False) -> dict:
    """Build + evaluate; returns the report payload.

    ``from_db`` scores the live ``qa_pairs`` knowledge base instead of the frozen
    KB fixture; ``local_only=True`` loads the encoder from the local cache only
    (fails fast when weights are absent), so callers can skip on offline boxes.
    """
    if model_name:
        settings.embedding_model_name = model_name
    try:
        embedding_service.warmup(local_files_only=local_only)
    except Exception as e:  # sentence-transformers raises on missing/offline weights
        raise ModelUnavailableError(f"无法加载向量模型 {settings.embedding_model_name}: {e}") from e

    entries = build_entries_from_db() if from_db else build_entries()
    matches = compute_top_matches(entries)
    rows = sweep(matches)
    best = choose_operating_point(rows)
    current = metrics_at(settings.chat_similarity_threshold, matches)
    return {
        "model_name": settings.embedding_model_name,
        "threshold": settings.chat_similarity_threshold,
        "source": "db" if from_db else "file",
        "n_entries": len(entries),
        "rows": rows,
        "best": best,
        "current": current,
        "matches": matches,
        "latency_p50_ms": _percentile([m.latency_ms for m in matches], 50),
        "latency_p95_ms": _percentile([m.latency_ms for m in matches], 95),
    }


def main(argv: list[str] | None = None) -> int:
    global MIN_PRECISION
    parser = argparse.ArgumentParser(description="Tune the chat semantic-match threshold.")
    parser.add_argument("--model", default=None, help="Override EMBEDDING_MODEL_NAME for this run")
    parser.add_argument("--output", default="chat_tuning_report.md", help="Report markdown path")
    parser.add_argument("--min-precision", type=float, default=MIN_PRECISION, help="Precision floor")
    parser.add_argument("--from-db", action="store_true", help="Score the live qa_pairs knowledge base")
    args = parser.parse_args(argv)

    MIN_PRECISION = args.min_precision

    try:
        result = run_eval(args.model, from_db=args.from_db)
    except ModelUnavailableError as e:
        print(f"跳过：{e}", file=sys.stderr)
        return 2

    write_report(Path(args.output), result["model_name"], result["rows"], result["best"], result["matches"])
    cur = result["current"]
    best = result["best"]
    src = "数据库 qa_pairs" if result["source"] == "db" else "冻结评测集 KB"
    print(f"知识库来源：{src}（{result['n_entries']} 条），模型 {result['model_name']}")
    print(
        f"当前阈值 {result['threshold']:.2f}: precision={cur.precision:.3f} recall={cur.recall:.3f} "
        f"F1={cur.f1:.3f} 回退准确率={cur.fallback_accuracy:.3f} (TP={cur.tp} FP={cur.fp} FN={cur.fn} TN={cur.tn})"
    )
    if best:
        print(
            f"推荐 YKM_CHAT_SIMILARITY_THRESHOLD = {best.threshold:.2f} "
            f"(precision={best.precision:.3f}, recall={best.recall:.3f})"
        )
    else:
        print("未找到满足精确率下限的阈值，详见报告")
    print(f"延迟 p50={result['latency_p50_ms']:.1f}ms p95={result['latency_p95_ms']:.1f}ms")
    print(f"报告已写入 {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
