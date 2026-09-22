"""Benchmark candidate embedding encoders for the chat semantic matcher.

The production encoder (``paraphrase-multilingual-MiniLM-L12-v2``) is small and
fast but only loosely Chinese-aware. This script scores it against stronger
multilingual / Chinese-first encoders on the frozen eval set used by
``tune_chat_threshold.py``, so the numbers are directly comparable with the
existing tuning reports.

Two knowledge-base views are scored for every candidate:

* ``full``      — canonical question + all variants (the production KB).
* ``canonical`` — canonical question only. Strip the paraphrase crutches and
                  the run measures how far the encoder alone bridges wording.

Per query we keep the *pair-level* ranked scores, so threshold sweeps, ranking
accuracy, confidence margins and false-fire rates are all recomputed in the
aggregation step from one JSON dump per candidate (re-analyse without re-encoding).

Each candidate runs in its own subprocess: 0.6B-parameter encoders hold
gigabytes of weights, and a fresh process keeps the measured peak RSS honest.

Weights are read from the local HF cache only (``HF_HUB_OFFLINE=1``) — huggingface.co
is unreachable from this box, so a candidate that was never fetched is skipped
instead of stalling the sweep. Pre-fetch with ``huggingface_hub.snapshot_download``
against ``HF_ENDPOINT=https://hf-mirror.com`` first (note: hf-mirror proxies >100MB
LFS files through a Xet bridge that read-times out here — ModelScope's CDN does not).

``BAAI/bge-base-zh-v1.5`` and ``BAAI/bge-m3`` ship only ``pytorch_model.bin``, which
transformers refuses to load on torch < 2.6 (CVE-2025-32434). Run those candidates
with a newer torch on ``PYTHONPATH`` (e.g. ``pip install --target <dir> torch``).

Usage (from backend/):
    python scripts/bench_embedding_models.py --list
    python scripts/bench_embedding_models.py --all --out-dir ../../tmp_export/bench
    python scripts/bench_embedding_models.py --model qwen3-06b --json ../../tmp_export/bench/qwen3-06b.json
    python scripts/bench_embedding_models.py --report --out-dir ../../tmp_export/bench
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Cache-only: never let a benchmark run stall on a network download.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Make `app` importable whether run as a script or a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.tune_chat_threshold import (  # noqa: E402
    EVAL_PATH,
    KB_PATH,
    ModelUnavailableError,
    TopMatch,
    sweep,
)  # noqa: E402

# ── Candidates ──────────────────────────────────────────────────────────────

# BGE's retrieval instruction for Chinese corpora.
_BGE_QUERY_INSTRUCT = "为这个句子生成表示以用于检索相关文章："
# Qwen3-Embedding's recommended task instruction for query-side encoding.
_QWEN_QUERY_INSTRUCT = "Instruct: 给定中文客服场景下的用户提问，检索与该提问语义等价的标准问题\nQuery: "


@dataclass(frozen=True)
class Candidate:
    key: str
    repo: str
    label: str
    query_prefix: str | None = None
    # Name under tmp_export/models/ when the weights were fetched into the
    # workspace instead of the shared HF cache (sandboxed runs cannot write to
    # ~/.cache/huggingface). Loaded by path when that directory exists.
    slug: str | None = None


MODELS_ROOT = Path(__file__).resolve().parents[3] / "tmp_export" / "models"


def resolve_repo(cand: Candidate) -> str:
    """Prefer a workspace-local snapshot dir over the Hub id when present."""
    if cand.slug:
        local = MODELS_ROOT / cand.slug
        if (local / "config.json").exists():
            return str(local)
    return cand.repo


# Task framings for the "-goal" candidates. Qwen3-Embedding documents the
# ``Instruct: ...\nQuery: ...`` form; the bare prefix is the BGE-style
# natural-language form, also tried on models without instruction training as an
# out-of-distribution control.
_GOAL_INSTRUCT = "匹配与用户问题意图相同、预期答案相同的预设问题"
_GOAL_BARE = f"{_GOAL_INSTRUCT}："
_GOAL_QWEN = "Instruct: " + _GOAL_INSTRUCT + "\nQuery: "

CANDIDATES: list[Candidate] = [
    Candidate("minilm-l12", "paraphrase-multilingual-MiniLM-L12-v2", "MiniLM-L12 v2（当前基线）"),
    Candidate("mpnet-base", "paraphrase-multilingual-mpnet-base-v2", "MPNet-base v2"),
    Candidate("bge-small-zh", "BAAI/bge-small-zh-v1.5", "BGE small zh 1.5"),
    Candidate(
        "bge-base-zh",
        "BAAI/bge-base-zh-v1.5",
        "BGE base zh 1.5",
        slug="bge-base-zh",
    ),
    Candidate(
        "bge-base-zh-retr",
        "BAAI/bge-base-zh-v1.5",
        "BGE base zh 1.5 + 检索指令",
        query_prefix=_BGE_QUERY_INSTRUCT,
        slug="bge-base-zh",
    ),
    Candidate("bge-m3", "BAAI/bge-m3", "BGE M3", slug="bge-m3"),
    Candidate("qwen3-06b", "Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding 0.6B", slug="qwen3-06b"),
    Candidate(
        "qwen3-06b-inst",
        "Qwen/Qwen3-Embedding-0.6B",
        "Qwen3-Embedding 0.6B + 检索指令",
        query_prefix=_QWEN_QUERY_INSTRUCT,
        slug="qwen3-06b",
    ),
    Candidate(
        "jina-v5-tm",
        "jinaai/jina-embeddings-v5-text-small-text-matching",
        "Jina v5 text-small（文本匹配适配器）",
        slug="jina-v5-tm",
    ),
    Candidate(
        "jina-v5-retr",
        "jinaai/jina-embeddings-v5-text-small-retrieval",
        "Jina v5 text-small（检索适配器）",
        query_prefix="Query: ",
        slug="jina-v5-retr",
    ),
    # Same encoders, but the instruction describes *this* task (same intent, same
    # expected answer) instead of generic retrieval — the control for whether the
    # retrieval wording was the problem or the score calibration is.
    Candidate(
        "minilm-goal",
        "paraphrase-multilingual-MiniLM-L12-v2",
        "MiniLM-L12 v2 + 任务目标指令（对照）",
        query_prefix=_GOAL_BARE,
    ),
    Candidate(
        "jina-v5-tm-goal",
        "jinaai/jina-embeddings-v5-text-small-text-matching",
        "Jina v5 文本匹配 + 任务目标指令",
        query_prefix=_GOAL_BARE,
        slug="jina-v5-tm",
    ),
    Candidate(
        "qwen3-06b-goal",
        "Qwen/Qwen3-Embedding-0.6B",
        "Qwen3-Embedding 0.6B + 任务目标指令",
        query_prefix=_GOAL_QWEN,
        slug="qwen3-06b",
    ),
]

VIEWS = ("full", "canonical")

# Wider than the production sweep (0.55–0.95): several strong encoders put every
# cosine in the 0.9x band, so a capped sweep would deny them any usable operating
# point purely because of score calibration, not representation quality.
SWEEP_LO = 0.50
SWEEP_HI = 0.995
SWEEP_STEP = 0.005


# ── Encoding ────────────────────────────────────────────────────────────────


@dataclass
class QueryResult:
    query: str
    expected: str | None
    encode_ms: float
    ranked: list[list[object]] = field(default_factory=list)  # [[pair_id, score], ...] best first


def _count_params(model) -> int:
    """Total encoder parameters, via whichever sentence-transformers API version is present."""
    for getter in (
        lambda: model.num_parameters(),
        lambda: model[0].num_parameters(),
        lambda: sum(p.numel() for p in model[0].parameters()),
    ):
        try:
            return int(getter())
        except Exception:
            continue
    return -1


def _run_candidate_meta(model, load_s: float, kb_encode_s: dict[str, float]) -> dict:
    return {
        "dim": int(model.get_sentence_embedding_dimension()),
        "params": _count_params(model),
        "max_seq_length": int(getattr(model, "max_seq_length", -1) or -1),
        "load_s": round(load_s, 2),
        "kb_encode_s": {k: round(v, 2) for k, v in kb_encode_s.items()},
        "peak_rss_mb": _peak_rss_mb(),
    }


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _peak_rss_mb() -> float | None:
    """Peak working set of this process in MB (Windows PSAPI; None elsewhere)."""
    if not sys.platform.startswith("win"):
        return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    c = Counters()
    c.cb = ctypes.sizeof(Counters)
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_uint32]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
        return None
    return c.PeakWorkingSetSize / 1e6


def _ranked_pairs(query_emb: list[float], entries: list) -> list[list[object]]:
    """Pair-level ranking of one query: each entry contributes its best phrasing."""
    from app.services.embedding_service import compute_similarity

    scored: list[tuple[str, float]] = []
    for entry in entries:
        best = max(
            (compute_similarity(query_emb, emb) for emb in entry.embeddings if emb),
            default=float("-inf"),
        )
        scored.append((entry.id, best))
    scored.sort(key=lambda s: -s[1])
    return [[pid, round(score, 6)] for pid, score in scored]


def run_candidate(cand: Candidate) -> dict:
    """Encode the KB + eval set with one candidate; return the raw dump."""
    from app.core.config import settings
    from app.services import embedding_service
    from app.services.embedding_service import QACacheEntry

    settings.embedding_model_name = resolve_repo(cand)
    t0 = time.perf_counter()
    last_error: Exception | None = None
    for local_only in (True, False):
        # Cache first (fails fast); then one online attempt for repos whose
        # offline refs are missing — huggingface.co is blocked here, so that
        # retry is slow but bounded, and a total miss still skips the candidate.
        os.environ["HF_HUB_OFFLINE"] = "1" if local_only else "0"
        try:
            embedding_service.warmup(local_files_only=local_only)
            last_error = None
            break
        except Exception as e:  # weights absent → caller marks the candidate skipped
            last_error = e
    if last_error is not None:
        raise ModelUnavailableError(f"无法加载向量模型 {settings.embedding_model_name}: {last_error}") from last_error
    load_s = time.perf_counter() - t0

    # Private accessor on purpose: the benchmark needs the raw encoder for
    # dim / param-count introspection that the service API does not expose.
    model = embedding_service._get_default_model(local_files_only=True)

    kb_rows = _load_jsonl(KB_PATH)
    eval_rows = _load_jsonl(EVAL_PATH)

    views: dict[str, list[QueryResult]] = {}
    kb_encode_s: dict[str, float] = {}
    for view in VIEWS:
        entries: list[QACacheEntry] = []
        t_kb = time.perf_counter()
        for r in kb_rows:
            texts = [r["question"], *r.get("question_variants", [])] if view == "full" else [r["question"]]
            entries.append(
                QACacheEntry(
                    id=r["id"],
                    question=r["question"],
                    category=r.get("category"),
                    embeddings=embedding_service.compute_embeddings(texts),
                    answer=r.get("answer", ""),
                )
            )
        kb_encode_s[view] = time.perf_counter() - t_kb

        results: list[QueryResult] = []
        for r in eval_rows:
            text = (cand.query_prefix or "") + r["query"]
            t_q = time.perf_counter()
            qe = embedding_service.compute_embedding(text)
            encode_ms = (time.perf_counter() - t_q) * 1000
            results.append(
                QueryResult(
                    query=r["query"],
                    expected=r.get("expected"),
                    encode_ms=encode_ms,
                    ranked=_ranked_pairs(qe, entries),
                )
            )
        views[view] = results

    return {
        "key": cand.key,
        "repo": resolve_repo(cand),
        "repo_id": cand.repo,
        "label": cand.label,
        "query_prefix": cand.query_prefix,
        "meta": _run_candidate_meta(model, load_s, kb_encode_s),
        "views": {view: [asdict(q) for q in rows] for view, rows in views.items()},
    }


# ── Metrics from a dump ─────────────────────────────────────────────────────


OFF_TOPIC_HINTS = ("天气", "登录", "密码", "人工客服", "备份", "导出报表", "流程", "绩效")


def _top_matches(dump: dict, view: str) -> list[TopMatch]:
    out: list[TopMatch] = []
    for q in dump["views"][view]:
        ranked = q["ranked"]
        out.append(
            TopMatch(
                query=q["query"],
                expected=q["expected"],
                pair_id=ranked[0][0] if ranked else None,
                score=ranked[0][1] if ranked else 0.0,
                latency_ms=q["encode_ms"],
            )
        )
    return out


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _operating_point(rows: list, floor: float, near_miss: list[TopMatch]) -> dict | None:
    """Highest-recall threshold (within the sweep) whose precision clears ``floor``."""
    eligible = [m for m in rows if m.precision >= floor]
    if not eligible:
        return None
    best_recall = max(m.recall for m in eligible)
    best = max((m for m in eligible if m.recall == best_recall), key=lambda m: m.threshold)
    fired = sum(1 for m in near_miss if m.score >= best.threshold)
    return {
        "threshold": best.threshold,
        "precision": best.precision,
        "recall": best.recall,
        "f1": best.f1,
        "fallback_accuracy": best.fallback_accuracy,
        "near_miss_false_fire_rate": (fired / len(near_miss)) if near_miss else 0.0,
    }


def _separation(dump: dict, view: str) -> tuple[float, float, float]:
    """(auroc, mean correct-top1 score, max negative score) for one view.

    AUROC = P(a positive's correct-pair score beats a negative's best score) —
    a threshold-free read of how well the encoder separates real hits from
    out-of-scope questions, which is what the fallback decision depends on.
    """
    pos_scores = []
    neg_scores = []
    for q in dump["views"][view]:
        if not q["ranked"]:
            continue
        if q["expected"] is not None:
            by_pair = dict(q["ranked"])
            if q["expected"] in by_pair:
                pos_scores.append(by_pair[q["expected"]])
        else:
            neg_scores.append(q["ranked"][0][1])
    if not pos_scores or not neg_scores:
        return (0.0, 0.0, 0.0)
    wins = sum(1 for p in pos_scores for nn in neg_scores if p > nn)
    ties = sum(1 for p in pos_scores for nn in neg_scores if p == nn)
    auroc = (wins + 0.5 * ties) / (len(pos_scores) * len(neg_scores))
    return (auroc, sum(pos_scores) / len(pos_scores), max(neg_scores))


def score_dump(dump: dict) -> dict:
    """Turn one candidate dump into the comparison-row metrics."""
    out: dict[str, dict] = {}
    for view in VIEWS:
        matches = _top_matches(dump, view)
        positives = [m for m in matches if m.expected is not None]
        negatives = [m for m in matches if m.expected is None]
        near_miss = [m for m in negatives if not any(h in m.query for h in OFF_TOPIC_HINTS)]
        hits = sum(1 for m in positives if m.pair_id == m.expected)
        lo, hi = _wilson(hits, len(positives))
        rows = sweep(matches, lo=SWEEP_LO, hi=SWEEP_HI, step=SWEEP_STEP)
        margins = [
            (q["ranked"][0][1] - q["ranked"][1][1])
            for q in dump["views"][view]
            if len(q["ranked"]) > 1 and q["expected"] is not None and q["ranked"][0][0] == q["expected"]
        ]
        auroc, pos_mean, neg_max = _separation(dump, view)
        lats = [m.latency_ms for m in matches]

        best_f1 = max(rows, key=lambda m: m.f1)
        out[view] = {
            "rank1": hits / len(positives) if positives else 0.0,
            "rank1_ci": [round(lo, 3), round(hi, 3)],
            "auroc": auroc,
            "pos_mean_score": pos_mean,
            "neg_max_score": neg_max,
            "margin_mean": sum(margins) / len(margins) if margins else 0.0,
            "op_p95": _operating_point(rows, 0.95, near_miss),
            "op_p90": _operating_point(rows, 0.90, near_miss),
            "best_f1": {
                "threshold": best_f1.threshold,
                "precision": best_f1.precision,
                "recall": best_f1.recall,
                "f1": best_f1.f1,
            },
            "latency_p50_ms": _percentile(lats, 50),
            "latency_p95_ms": _percentile(lats, 95),
            "n_pos": len(positives),
            "n_neg": len(negatives),
            "n_near_miss": len(near_miss),
        }
    return out


# ── Report ──────────────────────────────────────────────────────────────────


def _fmt(value: float | None, spec: str = ".3f", na: str = "—") -> str:
    return na if value is None else format(value, spec)


def write_comparison(dumps: list[dict], path: Path) -> None:
    scored = [(d, score_dump(d)) for d in dumps]
    n_eval = len(_load_jsonl(EVAL_PATH))
    n_kb = len(_load_jsonl(KB_PATH))
    lines = ["# 语义向量模型横评（chat 语义匹配）", ""]
    lines += [
        f"- 评测集：`{EVAL_PATH.name}`（{n_eval} 条查询）/ 知识库：`{KB_PATH.name}`（{n_kb} 组问答）",
        "- rank1：不设阈值时，全局最优命中正确问答组的正样本比例（Wilson 95% 置信区间见明细）",
        "- AUROC：正样本正确组得分高于负样本最高分的概率，衡量“命中 vs 回退”的可分性",
        "- 工作点：精确率下限约束下召回率最高的阈值；扫描区间 "
        f"{SWEEP_LO:.2f}–{SWEEP_HI:.2f}（step {SWEEP_STEP:g}），比生产调参的 0.55–0.95 更宽，"
        "以免分数分布偏高的模型仅因标定问题被判为无可用阈值",
        "",
    ]

    for view, title in (("full", "完整知识库（标准问题 + 相似问法）"), ("canonical", "仅标准问题（剥离问法增强）")):
        lines += [f"## {title}", ""]
        lines += [
            "| 模型 | 维度 | rank1 | AUROC | 置信差 | 阈值(P≥0.95) | 召回 | 误触发率 | 最佳 F1 | p50 ms | p95 ms |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for d, s in scored:
            m = s[view]
            op = m["op_p95"]
            lines.append(
                f"| {d['label']} | {d['meta']['dim']} | {m['rank1']:.3f} | {m['auroc']:.3f} "
                f"| {m['margin_mean']:.3f} | {_fmt(op and op['threshold'], '.2f')} | {_fmt(op and op['recall'])} "
                f"| {_fmt(op and op['near_miss_false_fire_rate'])} "
                f"| {m['best_f1']['f1']:.3f} | {m['latency_p50_ms']:.1f} | {m['latency_p95_ms']:.1f} |"
            )
        lines.append("")

    lines += [
        "## 体积与资源",
        "",
        "| 模型 | 仓库 | 参数量 | 维度 | 权重加载 s | KB 编码 s | 峰值内存 MB |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for d, _s in scored:
        meta = d["meta"]
        rss = meta["peak_rss_mb"]
        lines.append(
            f"| {d['label']} | `{d.get('repo_id', d['repo'])}` | {meta['params'] / 1e6:.0f}M | {meta['dim']} "
            f"| {meta['load_s']:.1f} | {meta['kb_encode_s']['full']:.2f} | {_fmt(rss, '.0f')} |"
        )
    lines.append("")

    lines += ["## 明细", ""]
    for d, s in scored:
        lines += [f"### {d['label']} (`{d.get('repo_id', d['repo'])}`)", ""]
        for view in VIEWS:
            m = s[view]
            lo, hi = m["rank1_ci"]
            lines.append(
                f"- {view}: rank1 {m['rank1']:.3f}（95% CI {lo:.2f}–{hi:.2f}，{m['n_pos']} 正样本）"
                f"，AUROC {m['auroc']:.3f}，正样本均分 {m['pos_mean_score']:.3f}"
                f" / 负样本最高分 {m['neg_max_score']:.3f}"
            )
            if m["op_p95"]:
                o = m["op_p95"]
                lines.append(
                    f"  - P≥0.95 工作点：阈值 {o['threshold']:.2f}，召回 {o['recall']:.3f}"
                    f"，回退准确率 {o['fallback_accuracy']:.3f}，"
                    f"近似负样本误触发率 {o['near_miss_false_fire_rate']:.3f}（{m['n_near_miss']} 条）"
                )
            else:
                lines.append("  - P≥0.95 工作点：0.55–0.95 区间内不存在（该知识库下精确率无法达标）")
            if m["op_p90"]:
                o = m["op_p90"]
                lines.append(
                    f"  - P≥0.90 工作点：阈值 {o['threshold']:.2f}，召回 {o['recall']:.3f}"
                    f"，误触发率 {o['near_miss_false_fire_rate']:.3f}"
                )
            b = m["best_f1"]
            lines.append(
                f"  - 最佳 F1：阈值 {b['threshold']:.2f} → F1 {b['f1']:.3f}"
                f"（P {b['precision']:.3f} / R {b['recall']:.3f}）"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Orchestration ───────────────────────────────────────────────────────────


def _dump_path(out_dir: Path, key: str) -> Path:
    return out_dir / f"{key}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark chat embedding encoders.")
    parser.add_argument("--list", action="store_true", help="Show candidates and exit")
    parser.add_argument("--model", default=None, help="Run one candidate key (single process)")
    parser.add_argument("--json", default=None, help="Where to write the single-candidate dump")
    parser.add_argument("--all", action="store_true", help="Run every candidate, one subprocess each")
    parser.add_argument("--report", action="store_true", help="Aggregate existing dumps into the comparison markdown")
    parser.add_argument("--out-dir", default="../../tmp_export/bench", help="Dump + report directory")
    args = parser.parse_args(argv)

    if args.list:
        for c in CANDIDATES:
            print(f"{c.key:16s} {c.repo:55s} {'LOCAL' if resolve_repo(c) != c.repo else 'CACHE':5s} {c.label}")
        return 0

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.model:
        cand = next((c for c in CANDIDATES if c.key == args.model), None)
        if cand is None:
            print(f"未知候选：{args.model}", file=sys.stderr)
            return 2
        try:
            dump = run_candidate(cand)
        except ModelUnavailableError as e:
            print(f"跳过：{e}", file=sys.stderr)
            return 3
        target = Path(args.json) if args.json else _dump_path(out_dir, cand.key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dump, ensure_ascii=False), encoding="utf-8")
        m = score_dump(dump)["full"]
        print(f"{cand.label}: rank1={m['rank1']:.3f} AUROC={m['auroc']:.3f} p95={m['latency_p95_ms']:.0f}ms → {target}")
        return 0

    if args.all:
        for cand in CANDIDATES:
            dest = _dump_path(out_dir, cand.key)
            cmd = [sys.executable, str(Path(__file__).resolve()), "--model", cand.key, "--json", str(dest)]
            print(f"▶ {cand.key} …", flush=True)
            proc = subprocess.run(
                cmd,
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            for stream in (proc.stdout, proc.stderr):
                if stream and stream.strip():
                    print(stream.strip(), flush=True)
            if proc.returncode not in (0,):
                print(f"  （{cand.key} 未产出结果，returncode={proc.returncode}）", flush=True)
        args.report = True

    if args.report:
        dumps = []
        for cand in CANDIDATES:
            p = _dump_path(out_dir, cand.key)
            if p.exists():
                dumps.append(json.loads(p.read_text(encoding="utf-8")))
        if not dumps:
            print("没有可聚合的结果文件", file=sys.stderr)
            return 2
        report = out_dir / "model_comparison.md"
        write_comparison(dumps, report)
        print(f"横评结果 {len(dumps)} 个模型 → {report}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
