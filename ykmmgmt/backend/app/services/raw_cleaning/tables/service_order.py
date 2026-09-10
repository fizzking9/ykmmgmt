"""Profile: 服务工单列表 (service_order, csv source).

Special handling on top of the common CSV cleanse:

  A2  the 提交参数 column is an *unescaped* JSON body (contains half-width
      commas and double quotes, never wrapped in quotes) — a naive split
      inflates the field count from 22/23 up to 34. Fix: locate the first
      ``{`` and brace-match the complete JSON (honoring string quotes and
      ``\\\\`` escapes inside).
  B1  column evolution — old exports have 22 columns (no 服务人员), newer
      ones have 23 → align by column name onto the 23-column superset,
      missing columns filled with "".

Idempotent: a standard-CSV row (JSON wrapped in quotes, escape already
restored) parses via the hand-written CSV parser to exactly 23 fields, so
the fast path is taken and the result is unchanged.
"""

import pandas as pd

from ..common import clean_cell, parse_csv_line, read_physical_lines, strip_trailing_empty

TABLE = "服务工单列表"
HEADER = [
    "工单号", "SN", "设备类型", "设备类型备注", "手机号", "服务类别", "服务项", "优先级",
    "状态", "备注", "登记时间", "激活时间", "分发时间", "完成时间", "处理时长", "登记人",
    "服务人员", "录入渠道", "处理节点", "处理人", "处理意见", "是否申诉", "提交参数",
]


def _extract_json(s: str, start: int) -> str | None:
    """Brace-match the complete JSON starting at ``s[start] == '{'``
    (handles quotes and backslash escapes inside strings)."""
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        i += 1
    return None


def clean_file(file) -> pd.DataFrame:
    lines = read_physical_lines(file)
    header = [clean_cell(x) for x in lines[0].split(",")]
    header_prefix = header[:-1]  # everything before 提交参数
    colmap = [header_prefix.index(c) if c in header_prefix else -1 for c in HEADER[:-1]]

    rows = []
    for s in lines[1:]:
        if s.strip() == "":
            continue
        # Fast path: standard CSV row (the JSON is quoted and escaped, as
        # in an already-cleansed file) → hand parser yields 23 fields.
        std = strip_trailing_empty([clean_cell(x) for x in parse_csv_line(s)])
        if len(std) == len(HEADER) and (std[-1] == "" or std[-1].lstrip().startswith("{")):
            j = std[-1]
            pf = std[:-1]
        else:
            # Dirty row: unescaped JSON inflates the field count → locate
            # the first '{' and brace-match the whole JSON body.
            idx = s.find("{")
            if idx != -1:
                j = _extract_json(s, idx) or ""
                pf = strip_trailing_empty([clean_cell(x) for x in s[:idx].split(",")])
            else:
                j = ""
                pf = strip_trailing_empty([clean_cell(x) for x in s.split(",")])
        row = [""] * len(HEADER)
        for ci in range(len(HEADER) - 1):
            k = colmap[ci]
            if 0 <= k < len(pf):
                row[ci] = pf[k]
        row[-1] = j
        rows.append(row)
    return pd.DataFrame(rows, columns=HEADER)
