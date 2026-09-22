"""Time-window consistency guard for semantic Q&A matching.

Embeddings rank 「上周总共接待了多少条？」 and 「本周总共接待了多少条？」 as
near-duplicates: they differ by one character, and every encoder we benchmarked is
largely blind to *which* calendar window a question asks about (see
tmp_export/embedding_model_benchmark.md — seeding 相似问法 pushed a 上周 question to
0.876 against a 本周 answer). Each preset question answers for exactly one window, so
serving yesterday's report to a last-week question is a wrong answer, not a near miss.

This module compares the two sides' time expressions *after* a match clears the
similarity threshold. It is deliberately permissive:

* text with no recognisable window returns an empty set, and an empty set never
  conflicts — so 「投诉积压情况怎么样？」 still matches as before;
* vague recency words (最近/近期/这段时间/一段时间) are not windows, because they
  genuinely can be answered by the current period's report;
* disagreement on *any* named window is a conflict, including across granularities
  (上周 asked, 昨日 registered) — the data period would be wrong either way.

Explicit dates (9月10日 / 2026-09-10) are out of scope: no pair in the knowledge base
is keyed on an absolute date, and guessing would only create silent false negatives.
"""

# group key -> surface forms. Substring matching, so no form may be a bare unit that
# another group's form contains (「上周」 vs 「上上周」 is handled by longest-first
# resolution plus consuming the matched characters below).
_WINDOW_FORMS: dict[str, tuple[str, ...]] = {
    "today": ("今天", "今日", "当天", "本日"),
    "yesterday": ("昨天", "昨日", "昨晚", "前一天"),
    "day_before_yesterday": ("前天", "前日"),
    "tomorrow": ("明天", "明日"),
    "this_week": ("本周", "这周", "这一周", "本星期", "当周"),
    "last_week": ("上周", "上星期", "上一周", "前一周"),
    "week_before_last": ("上上周", "上上星期"),
    "next_week": ("下周", "下星期", "下一周"),
    "this_month": ("本月", "这个月", "当月"),
    "last_month": ("上月", "上个月", "前一个月"),
    "next_month": ("下月", "下个月"),
    "this_quarter": ("本季", "本季度", "这个季度", "当季"),
    "last_quarter": ("上季", "上季度", "上个季度"),
    "next_quarter": ("下季", "下季度"),
    "this_year": ("今年", "本年", "本年度"),
    "last_year": ("去年", "上年", "上一年"),
    "next_year": ("明年", "下年"),
}

# Longer surface forms win: 「上上周」 must register as week_before_last only, never as
# last_week on its trailing two characters.
_ORDERED_FORMS: list[tuple[str, str]] = sorted(
    ((form, group) for group, forms in _WINDOW_FORMS.items() for form in forms),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


def time_windows(text: str) -> set[str]:
    """The calendar windows named in ``text``; empty when it names none.

    Several windows can be collected from one utterance (「上周和本周对比」 yields
    {last_week, this_week}), so a question comparing two periods still overlaps a
    pair keyed on either of them.
    """
    found: set[str] = set()
    remaining = text
    for form, group in _ORDERED_FORMS:
        if form in remaining:
            found.add(group)
            # Consume the match so a nested form cannot claim the same characters
            # (「上上周」 must not also register as 「上周」).
            remaining = remaining.replace(form, "\x00" * len(form), 1)
    return found


def windows_conflict(query: str, candidate_question: str) -> bool:
    """True when both sides name a window and none of them overlap.

    Either side naming no window is treated as unknown, not as a mismatch — the guard
    only ever removes matches it can positively prove wrong.
    """
    query_windows = time_windows(query)
    candidate_windows = time_windows(candidate_question)
    if not query_windows or not candidate_windows:
        return False
    return query_windows.isdisjoint(candidate_windows)
