"""Shared helpers for China A-share data providers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from tradingagents.dataflows.config import get_config


TS_CODE_RE = re.compile(r"^(?:\d{6}\.(?:SH|SZ|BJ)|\d{6}\.(?:CSI|CNI))$")


def validate_ts_code(ts_code: str) -> str:
    """Return an uppercase Tushare ts_code or raise ValueError."""
    symbol = (ts_code or "").strip().upper()
    if not TS_CODE_RE.match(symbol):
        raise ValueError(
            "A-share symbols must use Tushare ts_code format, e.g. "
            "000001.SZ, 600000.SH, 430047.BJ, or 000300.SH."
        )
    return symbol


def compact_ts_code(ts_code: str) -> str:
    """Convert 000001.SZ to 000001 for APIs that need the raw stock code."""
    return validate_ts_code(ts_code).split(".")[0]


def exchange_from_ts_code(ts_code: str) -> str:
    return validate_ts_code(ts_code).split(".")[1]


def date_to_tushare(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")


def date_from_tushare(date_str: str | int | None) -> str:
    if not date_str:
        return ""
    s = str(date_str)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def cache_dir(*parts: str) -> Path:
    base = Path(get_config()["data_cache_dir"])
    path = base.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def read_json_cache(path: Path, max_age_seconds: int | None = None) -> Any | None:
    if not path.exists():
        return None
    if max_age_seconds is not None:
        age = datetime.now().timestamp() - path.stat().st_mtime
        if age > max_age_seconds:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json_cache(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def dataframe_preview(df: pd.DataFrame, max_rows: int = 12) -> str:
    """Render a compact markdown-ish table without requiring tabulate."""
    if df is None or df.empty:
        return "_No rows returned._"
    view = df.head(max_rows).copy()
    view = view.fillna("")
    columns = [str(c) for c in view.columns]
    rows = [[str(v) for v in row] for row in view.to_numpy().tolist()]
    widths = [
        min(32, max(len(col), *(len(row[i]) for row in rows)) if rows else len(col))
        for i, col in enumerate(columns)
    ]

    def _clip(value: str, width: int) -> str:
        return value if len(value) <= width else value[: width - 1] + "..."

    header = "| " + " | ".join(_clip(c, widths[i]).ljust(widths[i]) for i, c in enumerate(columns)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = [
        "| " + " | ".join(_clip(cell, widths[i]).ljust(widths[i]) for i, cell in enumerate(row)) + " |"
        for row in rows
    ]
    suffix = f"\n\n_Showing {len(view)} of {len(df)} rows._"
    return "\n".join([header, sep, *body]) + suffix


def records_to_dataframe(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(list(records))


def token_status(env_name: str) -> str:
    return "configured" if os.getenv(env_name) else f"missing {env_name}"


def lookback_start(curr_date: str, days: int) -> str:
    return (parse_date(curr_date) - timedelta(days=days)).strftime("%Y-%m-%d")
