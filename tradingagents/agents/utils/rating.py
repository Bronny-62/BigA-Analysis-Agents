"""Shared 5-tier rating vocabulary and a deterministic heuristic parser.

The same five-tier scale (Buy, Overweight, Hold, Underweight, Sell) is used by:
- The Research Manager (investment plan recommendation)
- The Portfolio Manager (final position decision)
- The signal processor (rating extracted for downstream consumers)
- The memory log (rating tag stored alongside each decision entry)

Centralising it here avoids drift between those call sites.
"""

from __future__ import annotations

import re
from typing import Tuple


# Canonical, ordered 5-tier scale (most bullish to most bearish).
RATINGS_5_TIER: Tuple[str, ...] = (
    "Buy", "Overweight", "Hold", "Underweight", "Sell",
)

_RATING_SET = {r.lower() for r in RATINGS_5_TIER}
_RATING_ALIASES = {
    "buy": "Buy",
    "overweight": "Overweight",
    "hold": "Hold",
    "underweight": "Underweight",
    "sell": "Sell",
    "买入": "Buy",
    "增持": "Overweight",
    "持有": "Hold",
    "减持": "Underweight",
    "卖出": "Sell",
}

# Matches "Rating: X" / "评级：X" / "Rating: **X**" — tolerates markdown
# bold wrappers and either English or full-width separators.
_RATING_LABEL_RE = re.compile(
    r"(?:rating|评级).*?[:：\-－][\s*]*(\w+|买入|增持|持有|减持|卖出)",
    re.IGNORECASE,
)


def _canonical_rating(value: str) -> str | None:
    return _RATING_ALIASES.get(value.strip("*:：.,，。").lower())


def parse_rating(text: str, default: str = "Hold") -> str:
    """Heuristically extract a 5-tier rating from prose text.

    Two-pass strategy:
    1. Look for an explicit "Rating: X" label (tolerant of markdown bold).
    2. Fall back to the first 5-tier rating word found anywhere in the text.

    Returns a Title-cased rating string, or ``default`` if no rating word appears.
    """
    for line in text.splitlines():
        m = _RATING_LABEL_RE.search(line)
        if m:
            rating = _canonical_rating(m.group(1))
            if rating:
                return rating

    for line in text.splitlines():
        for alias, rating in _RATING_ALIASES.items():
            if not alias.isascii() and alias in line:
                return rating
        for word in line.lower().split():
            rating = _canonical_rating(word)
            if rating:
                return rating

    return default
