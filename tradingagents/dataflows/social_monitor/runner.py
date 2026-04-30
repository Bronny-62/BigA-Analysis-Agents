"""Runner for social monitor collection."""

from __future__ import annotations

import asyncio
import os
import time

from tradingagents.dataflows.a_share_utils import validate_ts_code

from .browser_collector import collect_target_async
from .sources import build_targets, parse_sources
from .storage import SocialMonitorStorage


def collect_once(
    symbols: list[str],
    sources: list[str] | None = None,
    scroll_seconds: int = 90,
    max_posts_per_symbol: int | None = None,
    headless: bool = True,
    max_pages_per_symbol: int | None = None,
) -> list[dict]:
    return asyncio.run(
        _collect_once_async(symbols, sources, scroll_seconds, max_posts_per_symbol, headless, max_pages_per_symbol)
    )


def collect_loop(
    symbols: list[str],
    sources: list[str] | None = None,
    scroll_seconds: int = 90,
    max_posts_per_symbol: int | None = None,
    headless: bool = True,
    max_pages_per_symbol: int | None = None,
) -> None:
    interval = int(os.getenv("SOCIAL_MONITOR_INTERVAL_SECONDS", "300") or 300)
    while True:
        collect_once(symbols, sources, scroll_seconds, max_posts_per_symbol, headless, max_pages_per_symbol)
        time.sleep(interval)


async def _collect_once_async(
    symbols: list[str],
    sources: list[str] | None,
    scroll_seconds: int,
    max_posts_per_symbol: int | None,
    headless: bool,
    max_pages_per_symbol: int | None,
) -> list[dict]:
    symbol_list = [validate_ts_code(symbol) for symbol in symbols]
    source_list = parse_sources(sources)
    storage = SocialMonitorStorage()
    results = []
    for target in build_targets(symbol_list, source_list):
        run_id = storage.begin_run(target.source, target.ts_code)
        try:
            posts = await collect_target_async(
                target,
                scroll_seconds=scroll_seconds,
                max_posts=max_posts_per_symbol,
                headless=headless,
                max_pages=max_pages_per_symbol,
            )
            inserted = storage.insert_posts(posts)
            storage.finish_run(run_id, "success", len(posts), inserted, "")
            results.append(
                {
                    "source": target.source,
                    "ts_code": target.ts_code,
                    "status": "success",
                    "posts_seen": len(posts),
                    "posts_inserted": inserted,
                    "error": "",
                }
            )
        except Exception as exc:
            storage.finish_run(run_id, "error", 0, 0, str(exc))
            results.append(
                {
                    "source": target.source,
                    "ts_code": target.ts_code,
                    "status": "error",
                    "posts_seen": 0,
                    "posts_inserted": 0,
                    "error": str(exc),
                }
            )
    return results

