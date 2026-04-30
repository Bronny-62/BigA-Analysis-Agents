"""Parsers for authorized social-monitor captures."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from .scoring import hotness_score, sentiment_for_text


def parse_json_posts(payload: Any, source: str, ts_code: str, platform_symbol: str) -> list[dict[str, Any]]:
    posts = []
    for item in _iter_items(payload):
        title = str(_pick(item, "title", "post_title", "subject") or "")
        content = str(_pick(item, "content", "text", "summary", "post_content") or "")
        text = f"{title} {content}".strip()
        if not text:
            continue
        author_obj = item.get("user") if isinstance(item.get("user"), dict) else {}
        author = _pick(item, "author", "nickname", "user_name") or _pick(author_obj, "screen_name", "name", "nickname")
        author_id = _pick(item, "author_id", "user_id") or _pick(author_obj, "id", "userId")
        created_at = str(_pick(item, "created_at", "createdAt", "publish_time", "time") or "")
        captured_at = datetime.now().isoformat(timespec="seconds")
        reply_count = _int(_pick(item, "reply_count", "commentCount", "comments"))
        like_count = _int(_pick(item, "like_count", "likeCount", "likes"))
        read_count = _int(_pick(item, "read_count", "viewCount", "views", "readCount"))
        repost_count = _int(_pick(item, "repost_count", "repostCount", "shares"))
        sentiment, sentiment_score = sentiment_for_text(text)
        post_id = str(_pick(item, "post_id", "id", "code") or _signature(source, ts_code, text, created_at))
        posts.append(
            {
                "source": source,
                "ts_code": ts_code,
                "platform_symbol": platform_symbol,
                "post_id": post_id,
                "title": title,
                "content": content,
                "author": str(author or ""),
                "author_id": str(author_id or ""),
                "created_at": created_at,
                "captured_at": captured_at,
                "reply_count": reply_count,
                "like_count": like_count,
                "read_count": read_count,
                "repost_count": repost_count,
                "url": str(_pick(item, "url", "link") or ""),
                "text_signature": _signature(source, ts_code, text, created_at),
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "hotness_score": hotness_score(read_count, reply_count, like_count, repost_count, created_at, captured_at),
                "confidence": "high" if post_id else "medium",
                "raw_json": json.dumps(item, ensure_ascii=False, default=str),
            }
        )
    return posts


def parse_html_posts(html: str, source: str, ts_code: str, platform_symbol: str) -> list[dict[str, Any]]:
    candidates = re.findall(r"<script[^>]*>(.*?)</script>", html or "", flags=re.S | re.I)
    for raw in candidates:
        raw = raw.strip()
        if not raw:
            continue
        match = re.search(r"(\{.*\}|\[.*\])", raw, flags=re.S)
        if not match:
            continue
        try:
            posts = parse_json_posts(json.loads(match.group(1)), source, ts_code, platform_symbol)
        except Exception:
            continue
        if posts:
            return posts
    return []


def _iter_items(value: Any):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(value, dict):
        return
    if _looks_like_post(value):
        yield value
    for key in ("items", "list", "posts", "data", "result", "records"):
        child = value.get(key)
        if child is value:
            continue
        yield from _iter_items(child)


def _looks_like_post(item: dict[str, Any]) -> bool:
    return any(key in item for key in ("title", "content", "text", "id", "post_id"))


def _pick(item: dict[str, Any], *keys: str):
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _signature(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:24]

