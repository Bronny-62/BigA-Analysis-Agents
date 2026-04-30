"""Cninfo announcement access for A-share fundamentals."""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests
from datetime import datetime

from .a_share_utils import (
    cache_dir,
    cache_key,
    compact_ts_code,
    dataframe_preview,
    read_json_cache,
    validate_ts_code,
    write_json_cache,
)


CNINFO_QUERY_URL = "https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1007"
CNINFO_ANNOUNCEMENT_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"


def get_cninfo_announcements(
    ts_code: str,
    start_date: str,
    end_date: str,
    categories: list[str] | None = None,
    limit: int = 30,
) -> str:
    ts_code = validate_ts_code(ts_code)
    params = {
        "scode": compact_ts_code(ts_code),
        "sdate": start_date,
        "edate": end_date,
    }
    if categories:
        params["category"] = ",".join(categories)

    path = cache_dir("cninfo") / f"announcements-{cache_key(params)}.json"
    cached = read_json_cache(path, max_age_seconds=3600)
    if cached is None:
        try:
            response = requests.get(CNINFO_QUERY_URL, params=params, timeout=12)
            response.raise_for_status()
            payload: Any = response.json()
        except Exception as exc:
            return (
                "Cninfo announcement query failed. The WebAPI endpoint may require "
                f"network access, throttling recovery, or parameter adjustment. Error: {exc}"
            )
        cached = payload
        write_json_cache(path, cached)

    rows = _extract_rows(cached)
    if not rows:
        rows = _query_cninfo_announcement_site(ts_code, start_date, end_date, categories, limit)
    if not rows:
        return f"No Cninfo announcements found for {ts_code} from {start_date} to {end_date}."
    df = pd.DataFrame(rows).head(limit)
    return f"## Cninfo announcements for {ts_code}\n\n{dataframe_preview(df, max_rows=limit)}"


def _query_cninfo_announcement_site(
    ts_code: str,
    start_date: str,
    end_date: str,
    categories: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    code = compact_ts_code(ts_code)
    exchange = ts_code.split(".")[1]
    org_prefix = {"SZ": "gssz", "SH": "gssh", "BJ": "gsbj"}.get(exchange, "gssz")
    plate = {"SZ": "sz", "SH": "sh", "BJ": "bj"}.get(exchange, "")
    column = {"SZ": "szse", "SH": "sse", "BJ": "bj"}.get(exchange, "")
    payload = {
        "pageNum": 1,
        "pageSize": min(max(limit, 1), 100),
        "column": column,
        "tabName": "fulltext",
        "plate": plate,
        "stock": f"{code},{org_prefix}0{code}",
        "searchkey": "",
        "secid": "",
        "category": ",".join(categories or []),
        "trade": "",
        "seDate": f"{start_date}~{end_date}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    }
    response = requests.post(CNINFO_ANNOUNCEMENT_URL, headers=headers, data=payload, timeout=12)
    response.raise_for_status()
    data = response.json()
    return _extract_rows({"announcements": data.get("announcements", [])})


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        candidates = payload.get("records") or payload.get("data") or payload.get("results") or payload.get("announcements")
    else:
        candidates = payload
    if isinstance(candidates, dict):
        candidates = candidates.get("records") or candidates.get("data") or []
    if not isinstance(candidates, list):
        return []

    rows = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        title = item.get("announcementTitle") or item.get("title") or item.get("secName") or ""
        date = _normalize_date(item.get("announcementTime") or item.get("announcementDate") or item.get("date") or item.get("f001d"))
        url = item.get("adjunctUrl") or item.get("url") or item.get("announcementUrl") or ""
        if url and not str(url).startswith("http"):
            url = "https://static.cninfo.com.cn/" + str(url).lstrip("/")
        rows.append(
            {
                "date": date,
                "title": title,
                "category": item.get("announcementType") or item.get("category") or "",
                "url": url,
                "summary": item.get("summary") or "",
            }
        )
    return rows


def _normalize_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    text = str(value)
    if text.isdigit():
        timestamp = int(text) / 1000 if len(text) > 10 else int(text)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    return text[:10]
