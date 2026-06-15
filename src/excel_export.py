"""Multi-sheet Excel export.

Builds a single .xlsx whose sheets mirror the `tables` of a `PipelineResult`
(same names, same order) — the equivalent of the `Export results` section of
each notebook. Returns raw bytes for a Streamlit `download_button`.
"""

from __future__ import annotations

import io
import re
from typing import Dict

import pandas as pd

# Excel sheet names: max 31 chars, no : \\ / ? * [ ]
_INVALID = re.compile(r"[:\\/?*\[\]]")


def _safe_sheet_name(name: str, used: set) -> str:
    clean = _INVALID.sub("-", str(name)).strip()[:31] or "Sheet"
    candidate = clean
    i = 1
    while candidate.lower() in used:
        suffix = f"_{i}"
        candidate = clean[: 31 - len(suffix)] + suffix
        i += 1
    used.add(candidate.lower())
    return candidate


def build_excel(tables: Dict[str, pd.DataFrame]) -> bytes:
    """Write every table to its own sheet and return the workbook bytes."""
    buffer = io.BytesIO()
    used: set = set()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        if not tables:
            pd.DataFrame({"info": ["No results"]}).to_excel(writer, sheet_name="Results", index=False)
        for name, df in tables.items():
            sheet = _safe_sheet_name(name, used)
            # Keep the index only when it carries information (named / non-range).
            keep_index = df.index.name is not None or not isinstance(df.index, pd.RangeIndex)
            df.to_excel(writer, sheet_name=sheet, index=keep_index)
    return buffer.getvalue()
