"""Source definitions for local social monitoring."""

from __future__ import annotations

from dataclasses import dataclass

from tradingagents.dataflows.a_share_utils import validate_ts_code

EASTMONEY_GUBA = "eastmoney_guba"
BINANCE_SQUARE = "binance_square"
SUPPORTED_SOURCES = {EASTMONEY_GUBA, BINANCE_SQUARE}


@dataclass(frozen=True)
class SourceTarget:
    source: str
    ts_code: str
    platform_symbol: str
    url: str


def parse_sources(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return [EASTMONEY_GUBA]
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    sources = [str(item).strip().lower() for item in items if str(item).strip()]
    for source in sources:
        if source not in SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported social monitor source: {source}")
    return sources or [EASTMONEY_GUBA]


def platform_symbol(ts_code: str, source: str) -> str:
    source = source.strip().lower()
    if source == EASTMONEY_GUBA:
        return validate_ts_code(ts_code).split(".")[0]
    if source == BINANCE_SQUARE:
        return ts_code.split("-")[0].upper()
    raise ValueError(f"Unsupported social monitor source: {source}")


def source_url(ts_code: str, source: str) -> str:
    symbol = platform_symbol(ts_code, source)
    if source == EASTMONEY_GUBA:
        return f"https://guba.eastmoney.com/list,{symbol}.html"
    if source == BINANCE_SQUARE:
        return "https://www.binance.com/zh-CN/square"
    raise ValueError(f"Unsupported social monitor source: {source}")


def build_targets(symbols: list[str], sources: list[str] | None = None) -> list[SourceTarget]:
    source_list = parse_sources(sources)
    return [
        SourceTarget(source=source, ts_code=symbol, platform_symbol=platform_symbol(symbol, source), url=source_url(symbol, source))
        for symbol in symbols
        for source in source_list
    ]

