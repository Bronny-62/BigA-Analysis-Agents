"""Simple scoring helpers for captured social posts."""

from __future__ import annotations

from datetime import datetime


def hotness_score(
    read_count: int | float | None,
    reply_count: int | float | None,
    like_count: int | float | None,
    repost_count: int | float | None,
    created_at: str | None,
    captured_at: str | None = None,
) -> float:
    reads = float(read_count or 0)
    replies = float(reply_count or 0)
    likes = float(like_count or 0)
    reposts = float(repost_count or 0)
    base = reads * 0.01 + replies * 3 + likes * 2 + reposts * 2.5
    age_hours = _hours_between(created_at, captured_at)
    decay = 0.5 ** max(age_hours, 0)
    return round(base * decay, 4)


def sentiment_for_text(text: str) -> tuple[str, float]:
    value = text or ""
    positive_words = ("利好", "看多", "突破", "上涨", "增长", "买入", "强势", "机会")
    negative_words = ("利空", "看空", "下跌", "大跌", "风险", "亏损", "卖出", "暴雷")
    positive = sum(1 for word in positive_words if word in value)
    negative = sum(1 for word in negative_words if word in value)
    if positive > negative:
        return "positive", min(1.0, 0.3 + positive * 0.1)
    if negative > positive:
        return "negative", max(-1.0, -0.3 - negative * 0.1)
    return "neutral", 0.0


def _hours_between(created_at: str | None, captured_at: str | None) -> float:
    try:
        start = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).replace(tzinfo=None)
        end = datetime.fromisoformat(str(captured_at or datetime.now().isoformat()).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return 0.0
    return max((end - start).total_seconds() / 3600, 0.0)

