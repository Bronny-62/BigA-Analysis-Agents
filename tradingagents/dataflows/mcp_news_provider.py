"""MCP-backed news providers plus local real-time event cache."""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from .a_share_utils import cache_dir, dataframe_preview, parse_date, validate_ts_code
from .config import get_config


OPENNEWS_API_BASE = "https://ai.6551.io"
OPENNEWS_WSS_URL = "wss://ai.6551.io/open/news_wss"
JIN10_MCP_URL = "https://mcp.jin10.com/mcp"


def _news_cache_path() -> Path:
    return cache_dir("news_events") / "events.jsonl"


async def call_remote_mcp_tool(server_url: str, token: str | None, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call a remote streamable HTTP MCP tool when MCP dependencies are installed."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        raise RuntimeError("MCP client dependencies are not installed.") from exc

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with streamablehttp_client(server_url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def _call_mcp_sync(server_url: str, token: str | None, tool_name: str, arguments: dict[str, Any]) -> Any:
    try:
        return asyncio.run(call_remote_mcp_tool(server_url, token, tool_name, arguments))
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"MCP call {tool_name} failed: {exc}") from exc


def _opennews_token() -> str:
    return (os.getenv("OPENNEWS_TOKEN") or "").strip()


def _call_opennews_rest(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Call the official OpenNews REST API used by opennews-mcp.

    The opennews-mcp repository runs a local stdio MCP server whose tools call
    POST /open/news_search on https://ai.6551.io. For this application we call
    that API directly by default, which avoids requiring a separate MCP process
    during CLI runs while preserving the same data source and token semantics.
    """
    token = _opennews_token()
    if not token:
        raise RuntimeError("OPENNEWS_TOKEN is not configured. Add OPENNEWS_TOKEN=<your-token> to .env.")

    max_rows = int(os.getenv("OPENNEWS_MAX_ROWS", "100") or 100)
    fetch_limit = min(max(max(1, limit), limit * 3), max_rows)
    base_url = os.getenv("OPENNEWS_API_BASE", OPENNEWS_API_BASE).rstrip("/")
    body: dict[str, Any] = {
        "q": query,
        "engineTypes": {"news": []},
        "limit": fetch_limit,
        "page": 1,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            response = client.post(f"{base_url}/open/news_search", json=body)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        raise RuntimeError(f"OpenNews REST HTTP {status}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"OpenNews REST request failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"OpenNews REST returned unexpected payload type: {type(payload).__name__}")
    if payload.get("success") is False:
        raise RuntimeError(str(payload.get("error") or payload))
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("OpenNews REST returned a payload without a list-valued data field.")
    return data


def _flatten_mcp_result(result: Any) -> list[dict[str, Any]]:
    raw = getattr(result, "content", result)
    if isinstance(raw, list):
        values = []
        for item in raw:
            text = getattr(item, "text", None)
            if text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        values.extend(parsed)
                    elif isinstance(parsed, dict):
                        values.append(parsed)
                    else:
                        values.append({"content": str(parsed)})
                except json.JSONDecodeError:
                    values.append({"content": text})
            elif isinstance(item, dict):
                values.append(item)
        return values
    if isinstance(raw, dict):
        data = raw.get("data") or raw.get("items") or raw.get("records") or raw
        if isinstance(data, dict):
            nested = data.get("items") or data.get("records") or data.get("results") or data.get("data")
            if isinstance(nested, list):
                return nested
        return data if isinstance(data, list) else [data]
    return [{"content": str(raw)}]


def search_a_share_news(query: str, start_date: str, end_date: str, limit: int = 20) -> str:
    rows = []
    opennews_error = None
    query_variants = _news_query_variants(query)
    for candidate in query_variants:
        try:
            mcp_url = (os.getenv("OPENNEWS_MCP_URL") or "").strip()
            if mcp_url:
                result = _call_mcp_sync(
                    mcp_url,
                    _opennews_token(),
                    "search_news",
                    {"keyword": candidate, "limit": limit},
                )
                opennews_items = _flatten_mcp_result(result)
            else:
                opennews_items = _call_opennews_rest(candidate, limit=limit)
            rows.extend(_filter_news_by_date(_normalize_news(opennews_items, "opennews"), start_date, end_date))
        except Exception as exc:
            opennews_error = str(exc)
        if rows:
            break

    if not rows:
        for candidate in query_variants:
            try:
                result = _call_mcp_sync(
                    os.getenv("JIN10_MCP_URL", JIN10_MCP_URL),
                    os.getenv("JIN10_MCP_TOKEN"),
                    "search_news",
                    {"keyword": candidate},
                )
                jin10_rows = _normalize_news(_flatten_mcp_result(result), "jin10")
                rows.extend(_filter_news_by_date(jin10_rows, start_date, end_date))
            except Exception as exc:
                if opennews_error:
                    return f"News MCP unavailable. opennews: {opennews_error}; jin10: {exc}"
                return f"Jin10 MCP fallback unavailable: {exc}"
            if rows:
                break

    return _format_news(f"A-share news search: {query}", rows, limit)


def get_cn_macro_news(curr_date: str, look_back_days: int = 7, limit: int = 30) -> str:
    start = (parse_date(curr_date) - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    query = "A股 OR 中国股市 OR 证监会 OR 央行 OR 财政部 OR 宏观经济 OR 政策"
    return search_a_share_news(query, start, curr_date, limit=limit)


def get_a_share_realtime_news(ts_code: str, look_back_minutes: int = 240, limit: int = 30) -> str:
    ts_code = validate_ts_code(ts_code)
    if not get_config().get("realtime_news_enabled", False):
        return (
            "Real-time news is disabled by configuration. Set realtime_news_enabled=True "
            "and run the opennews WebSocket subscriber to populate the local cache."
        )
    rows = []
    cutoff = datetime.now() - timedelta(minutes=look_back_minutes)
    code = ts_code.split(".")[0]
    for event in read_news_events():
        ts = _parse_ts(event.get("received_at") or event.get("published_at"))
        text = " ".join(str(event.get(k, "")) for k in ("title", "content", "symbols"))
        if ts and ts < cutoff:
            continue
        if ts_code in text or code in text:
            rows.append(event)
    if not rows:
        return (
            f"No cached real-time news found for {ts_code} in the last {look_back_minutes} minutes. "
            "Start the opennews WebSocket subscriber to populate the cache."
        )
    return _format_news(f"Cached real-time news for {ts_code}", rows, limit)


def append_news_event(event: dict[str, Any]) -> None:
    normalized = {
        "id": event.get("id") or event.get("newsId") or event.get("url") or "",
        "source": event.get("source") or event.get("platform") or "opennews",
        "title": event.get("title") or "",
        "content": event.get("content") or event.get("summary") or "",
        "url": event.get("url") or "",
        "published_at": event.get("published_at") or event.get("publishTime") or event.get("time") or event.get("ts") or "",
        "received_at": datetime.now().isoformat(timespec="seconds"),
        "symbols": event.get("symbols") or [],
        "signal": event.get("signal") or "",
        "score": event.get("score") or "",
        "raw": event,
    }
    path = _news_cache_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, default=str) + "\n")


def read_news_events(max_events: int = 1000) -> list[dict[str, Any]]:
    path = _news_cache_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-max_events:]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


async def subscribe_opennews_websocket() -> None:
    """Long-running subscriber for external scripts or future CLI commands."""
    import websockets

    token = _opennews_token()
    if not token:
        raise RuntimeError("OPENNEWS_TOKEN is not configured. Add OPENNEWS_TOKEN=<your-token> to .env.")
    url = os.getenv("OPENNEWS_WSS_URL", OPENNEWS_WSS_URL)
    separator = "&" if "?" in url else "?"
    async with websockets.connect(f"{url}{separator}token={token}") as ws:
        await ws.send(json.dumps({"method": "news.subscribe", "params": {"engineTypes": {"news": []}}}))
        async for message in ws:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue
            data = payload.get("params") or payload.get("data") or payload
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        append_news_event(item)
            elif isinstance(data, dict):
                append_news_event(data)


def _normalize_news(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for item in items:
        title = _clean_news_text(
            item.get("title") or item.get("headline") or item.get("content") or item.get("text") or ""
        )
        key = (title, item.get("url") or item.get("link") or "")
        if not title or key in seen:
            continue
        seen.add(key)
        summary = _clean_news_text(
            item.get("summary")
            or item.get("summaryZh")
            or _nested_get(item, ("aiRating", "summary"))
            or item.get("content")
            or item.get("text")
            or item.get("description")
            or ""
        )
        rows.append(
            {
                "source": item.get("source") or item.get("newsType") or item.get("type") or source,
                "time": (
                    item.get("published_at")
                    or item.get("publishTime")
                    or item.get("createdAt")
                    or item.get("time")
                    or item.get("timestamp")
                    or item.get("ts")
                    or item.get("date")
                    or ""
                ),
                "title": title,
                "summary": summary,
                "url": item.get("url") or item.get("link") or item.get("sourceUrl") or "",
                "signal": _nested_get(item, ("aiRating", "signal")) or item.get("signal") or "",
                "score": _nested_get(item, ("aiRating", "score")) or item.get("score") or "",
            }
        )
    return rows


def _news_query_variants(query: str) -> list[str]:
    base = " ".join(str(query or "").split())
    if not base:
        return [base]

    variants = [base]
    without_code = re.sub(r"\b\d{6}(?:\.(?:SZ|SH|BJ))?\b", " ", base, flags=re.IGNORECASE)
    without_code = " ".join(without_code.split())
    if without_code and without_code not in variants:
        variants.append(without_code)

    tokens = [token for token in re.split(r"\s+", without_code or base) if token and token.upper() != "OR"]
    if len(tokens) > 1:
        first_token = tokens[0]
        if re.search(r"[\u4e00-\u9fff]", first_token) and first_token not in variants:
            variants.append(first_token)

    return variants[:3]


def _clean_news_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:p|div|span|b|strong|em|i|section)[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _nested_get(item: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = item
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _filter_news_by_date(rows: list[dict[str, Any]], start_date: str, end_date: str) -> list[dict[str, Any]]:
    start = parse_date(start_date)
    end = parse_date(end_date) + timedelta(days=1)
    filtered = []
    saw_dated_row = False
    for row in rows:
        ts = _parse_ts(row.get("time"))
        if ts is None:
            continue
        saw_dated_row = True
        if start <= ts < end:
            filtered.append(row)
    if filtered:
        return filtered
    return [] if saw_dated_row else rows


def _format_news(title: str, rows: list[dict[str, Any]], limit: int) -> str:
    if not rows:
        return f"No news rows available for {title}."
    df = pd.DataFrame(rows).head(limit)
    return f"## {title}\n\n{dataframe_preview(df, max_rows=limit)}"


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None
