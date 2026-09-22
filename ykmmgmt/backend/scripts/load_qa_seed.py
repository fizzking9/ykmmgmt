"""Seed the Q&A knowledge base from the frozen example set.

Reads ``tests/data/qa_kb.jsonl`` (the three canonical Phase-17 examples from
``tmp_export/QAexample_formatted.md``), computes real embeddings for
``[question, *variants]``, and upserts each row into ``qa_pairs`` (matched on
the canonical question). Run from ``backend/``:

    python scripts/load_qa_seed.py

Set HF_HUB_OFFLINE=1 when the encoder weights are already cached (avoids any
network round-trip to huggingface.co).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make `app` importable whether run as a script or a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory, engine  # noqa: E402
from app.models.qa_pair import QAPair  # noqa: E402
from app.services import embedding_service  # noqa: E402

KB_PATH = Path(__file__).resolve().parents[1] / "tests" / "data" / "qa_kb.jsonl"


def _read_kb() -> list[dict]:
    return [json.loads(line) for line in KB_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


async def seed() -> int:
    rows = _read_kb()
    inserted = updated = 0
    async with async_session_factory() as session:
        for r in rows:
            variants = r.get("question_variants", [])
            embeddings = embedding_service.compute_embeddings([r["question"], *variants])
            existing = (
                await session.execute(select(QAPair).where(QAPair.question == r["question"]))
            ).scalar_one_or_none()
            if existing is not None:
                existing.question_variants = variants
                existing.answer = r["answer"]
                existing.category = r.get("category")
                existing.embeddings = embeddings
                existing.is_active = True
                updated += 1
            else:
                session.add(
                    QAPair(
                        question=r["question"],
                        question_variants=variants,
                        answer=r["answer"],
                        category=r.get("category"),
                        embeddings=embeddings,
                        is_active=True,
                    )
                )
                inserted += 1
        await session.commit()
    print(f"问答知识库写入完成：新增 {inserted}，更新 {updated}，共 {inserted + updated} 条")
    return 0


if __name__ == "__main__":

    async def _main() -> int:
        try:
            return await seed()
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(_main()))
