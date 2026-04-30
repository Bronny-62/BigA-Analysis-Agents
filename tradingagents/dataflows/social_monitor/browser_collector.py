"""Playwright collector for authorized social browser sessions."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from tradingagents.dataflows.a_share_utils import cache_dir

from .parser import parse_html_posts
from .sources import EASTMONEY_GUBA, SourceTarget


def profile_dir() -> Path:
    return cache_dir("browser_profile", "social_monitor")


async def collect_target_async(
    target: SourceTarget,
    scroll_seconds: int = 90,
    max_posts: int | None = None,
    headless: bool = True,
    max_pages: int | None = None,
) -> list[dict]:
    playwright_module = _import_playwright()
    async with playwright_module.async_playwright() as playwright:
        cdp_url = os.getenv("SOCIAL_BROWSER_CDP_URL", "").strip()
        close_page = False
        if cdp_url:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if getattr(browser, "contexts", None) else await browser.new_context()
            page = await context.new_page()
            close_page = True
        else:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir()),
                headless=headless,
                viewport={"width": 1440, "height": 1000},
            )
            page = await context.new_page()
        try:
            return await _collect_from_page(page, target, scroll_seconds, max_posts, max_pages)
        finally:
            if close_page and hasattr(page, "close"):
                await page.close()
            elif hasattr(context, "close"):
                await context.close()


async def _collect_from_page(
    page,
    target: SourceTarget,
    scroll_seconds: int = 90,
    max_posts: int | None = None,
    max_pages: int | None = None,
) -> list[dict]:
    await page.goto(target.url)
    if hasattr(page, "on"):
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
    pages = max(1, int(max_pages or 1))
    limit = max_posts or 200
    posts: list[dict] = []
    seen: set[str] = set()

    for page_number in range(1, pages + 1):
        if page_number > 1:
            if target.source == EASTMONEY_GUBA:
                await _goto_eastmoney_page(page, target.url, page_number)
            else:
                break
        await _raise_if_verification_page(page)
        if target.source != EASTMONEY_GUBA or _scroll_enabled_for_eastmoney():
            await _scroll(page, scroll_seconds)
        html = await page.content()
        for post in parse_html_posts(html, target.source, target.ts_code, target.platform_symbol):
            key = str(post.get("post_id") or post.get("text_signature") or post.get("url") or post)
            if key in seen:
                continue
            seen.add(key)
            if len(posts) >= limit:
                break
            posts.append(post)
        if len(posts) >= limit:
            break
    return posts


async def _goto_eastmoney_page(page, base_url: str, page_number: int) -> None:
    try:
        await page.get_by_text(str(page_number), exact=True).first().click(timeout=3000)
        await page.wait_for_load_state("domcontentloaded")
    except Exception:
        next_url = re.sub(r"(?:_\d+)?\.html$", f"_{page_number}.html", base_url)
        await page.goto(next_url)


async def _scroll(page, scroll_seconds: int) -> None:
    deadline = asyncio.get_event_loop().time() + max(scroll_seconds, 0)
    while asyncio.get_event_loop().time() <= deadline:
        mouse = getattr(page, "mouse", None)
        if mouse and hasattr(mouse, "wheel"):
            result = mouse.wheel(0, 1200)
            if hasattr(result, "__await__"):
                await result
        await page.wait_for_timeout(250)
        if scroll_seconds <= 0:
            break


async def _raise_if_verification_page(page) -> None:
    html = (await page.content()).lower()
    if any(marker in html for marker in ("captcha", "验证码", "安全验证", "verify")):
        raise RuntimeError("verification required")


def _scroll_enabled_for_eastmoney() -> bool:
    return os.getenv("SOCIAL_EASTMONEY_ENABLE_SCROLL", "").strip().lower() in {"1", "true", "yes", "on"}


def _import_playwright():
    from playwright import async_api

    return async_api

