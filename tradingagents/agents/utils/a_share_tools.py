"""LangChain tool schemas for China A-share analysis."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows import cninfo_provider, mcp_news_provider, social_provider, tushare_provider


@tool
def get_a_share_ohlcv(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
    freq: Annotated[str, "Bar frequency: D, W, or M"] = "D",
) -> str:
    """Retrieve China A-share OHLCV bars from Tushare."""
    return tushare_provider.get_a_share_ohlcv(ts_code, start_date, end_date, freq)


@tool
def get_a_share_market_snapshot(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    trade_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve daily market snapshot, valuation, liquidity, and limit-price context."""
    return tushare_provider.get_a_share_market_snapshot(ts_code, trade_date)


@tool
def get_a_share_indicators(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    trade_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
    look_back_days: Annotated[int, "Number of calendar days to load"] = 120,
    indicators: Annotated[list[str], "Indicator names such as macd, rsi, boll, close_20_sma"] = None,
) -> str:
    """Calculate technical indicators from Tushare daily bars."""
    return tushare_provider.get_a_share_indicators(ts_code, trade_date, look_back_days, indicators)


@tool
def get_a_share_moneyflow(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
) -> str:
    """Retrieve A-share money flow and dragon-tiger list context where available."""
    return tushare_provider.get_a_share_moneyflow(ts_code, start_date, end_date)


@tool
def get_a_share_social_sentiment(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
) -> str:
    """Retrieve compliance-first social sentiment proxy data from local cache and news signals."""
    return social_provider.get_a_share_social_sentiment(ts_code, start_date, end_date)


@tool
def get_a_share_hotness(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    trade_date: Annotated[str, "Trading date in YYYY-MM-DD format"],
) -> str:
    """Retrieve Tushare-provided market hotness/ranking data where permissions allow."""
    return social_provider.get_a_share_hotness(ts_code, trade_date)


@tool
def get_social_monitoring_coverage(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
) -> str:
    """Explain current social monitoring coverage, gaps, and confidence."""
    return social_provider.get_social_monitoring_coverage(ts_code)


@tool
def search_a_share_news(
    query: Annotated[str, "Chinese or English search query, can include stock name or ts_code"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
    limit: Annotated[int, "Maximum number of news items"] = 20,
) -> str:
    """Search A-share related news through opennews MCP with Jin10 MCP fallback."""
    return mcp_news_provider.search_a_share_news(query, start_date, end_date, limit)


@tool
def get_a_share_realtime_news(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    look_back_minutes: Annotated[int, "Minutes to look back in local real-time news cache"] = 240,
    limit: Annotated[int, "Maximum number of news items"] = 30,
) -> str:
    """Read cached real-time opennews WebSocket events for an A-share symbol."""
    return mcp_news_provider.get_a_share_realtime_news(ts_code, look_back_minutes, limit)


@tool
def get_cn_macro_news(
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of news items"] = 30,
) -> str:
    """Retrieve China macro, policy, and market-wide news."""
    return mcp_news_provider.get_cn_macro_news(curr_date, look_back_days, limit)


@tool
def get_a_share_company_profile(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
) -> str:
    """Retrieve A-share company profile from Tushare."""
    return tushare_provider.get_company_profile(ts_code)


@tool
def get_a_share_financials(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    report_type: Annotated[str, "income, balancesheet, cashflow, or fina_indicator"],
    period: Annotated[str, "Optional report period like 20231231"] = None,
) -> str:
    """Retrieve A-share structured financial statements and indicators from Tushare."""
    return tushare_provider.get_financials(ts_code, report_type, period)


@tool
def get_cninfo_announcements(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
    categories: Annotated[list[str], "Optional Cninfo announcement categories"] = None,
) -> str:
    """Retrieve Cninfo announcements for an A-share symbol."""
    return cninfo_provider.get_cninfo_announcements(ts_code, start_date, end_date, categories)


@tool
def get_a_share_announcements(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    start_date: Annotated[str, "Start date in YYYY-MM-DD format"],
    end_date: Annotated[str, "End date in YYYY-MM-DD format"],
    categories: Annotated[list[str], "Optional announcement categories"] = None,
) -> str:
    """Retrieve A-share announcements from Tushare anns_d first, with Cninfo fallback."""
    return tushare_provider.get_announcements(ts_code, start_date, end_date, categories)


@tool
def get_a_share_fundamental_snapshot(
    ts_code: Annotated[str, "Tushare ts_code, e.g. 000001.SZ or 600000.SH"],
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"],
) -> str:
    """Retrieve a compact A-share fundamental snapshot from Tushare."""
    return tushare_provider.get_fundamental_snapshot(ts_code, curr_date)
