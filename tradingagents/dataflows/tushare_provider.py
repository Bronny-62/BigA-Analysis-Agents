"""Tushare-backed A-share market and fundamental data."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import pandas as pd

from .a_share_utils import (
    cache_dir,
    cache_key,
    dataframe_preview,
    date_to_tushare,
    lookback_start,
    read_json_cache,
    validate_ts_code,
    write_json_cache,
)


class TushareProviderError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _pro_api():
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise TushareProviderError("TUSHARE_TOKEN is not configured.")
    try:
        import tushare as ts
    except ImportError as exc:
        raise TushareProviderError("The 'tushare' package is not installed.") from exc
    ts.set_token(token)
    return ts.pro_api(token)


def _call(name: str, max_age_seconds: int | None = 3600, **kwargs: Any) -> pd.DataFrame:
    path = cache_dir("tushare") / f"{name}-{cache_key(kwargs)}.json"
    cached = read_json_cache(path, max_age_seconds=max_age_seconds)
    if cached is not None:
        return pd.DataFrame(cached)

    pro = _pro_api()
    func = getattr(pro, name)
    df = func(**kwargs)
    if df is None:
        df = pd.DataFrame()
    write_json_cache(path, df.to_dict(orient="records"))
    return df


def _format_section(title: str, df: pd.DataFrame, max_rows: int = 12) -> str:
    return f"## {title}\n\n{dataframe_preview(df, max_rows=max_rows)}"


def get_a_share_ohlcv(ts_code: str, start_date: str, end_date: str, freq: str = "D") -> str:
    ts_code = validate_ts_code(ts_code)
    freq = (freq or "D").upper()
    if freq not in {"D", "W", "M"}:
        return "Tushare 5000-point configuration uses daily/weekly/monthly bars here; iFinD is reserved for intraday data."

    api_name = {"D": "daily", "W": "weekly", "M": "monthly"}[freq]
    df = _call(
        api_name,
        ts_code=ts_code,
        start_date=date_to_tushare(start_date),
        end_date=date_to_tushare(end_date),
    )
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date")
    return _format_section(
        f"A-share OHLCV ({ts_code}, {start_date} to {end_date}, freq={freq})",
        df,
        max_rows=20,
    )


def get_daily_frame(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    ts_code = validate_ts_code(ts_code)
    df = _call(
        "daily",
        ts_code=ts_code,
        start_date=date_to_tushare(start_date),
        end_date=date_to_tushare(end_date),
    )
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date")
    return df


def get_a_share_market_snapshot(ts_code: str, trade_date: str) -> str:
    from . import ifind_provider

    ts_code = validate_ts_code(ts_code)
    d = date_to_tushare(trade_date)
    sections = []
    daily = _call("daily", ts_code=ts_code, start_date=d, end_date=d)
    basic = _call("daily_basic", ts_code=ts_code, trade_date=d)
    limit = _safe_call("stk_limit", ts_code=ts_code, trade_date=d)
    sections.append(_format_section(f"Daily bar for {ts_code} on {trade_date}", daily))
    sections.append(_format_section("Daily valuation/liquidity snapshot", basic))
    if limit is not None and not limit.empty:
        sections.append(_format_section("Limit-up/limit-down reference", limit))
    ifind_section = ifind_provider.optional_section("iFinD real-time quote unavailable", ifind_provider.real_time_quote, ts_code)
    if ifind_section:
        sections.append(ifind_section)
    return "\n\n".join(sections)


def _safe_call(name: str, **kwargs: Any) -> pd.DataFrame | None:
    try:
        return _call(name, **kwargs)
    except Exception:
        return None


def get_a_share_moneyflow(ts_code: str, start_date: str, end_date: str) -> str:
    ts_code = validate_ts_code(ts_code)
    sections = []
    moneyflow = _safe_call(
        "moneyflow",
        ts_code=ts_code,
        start_date=date_to_tushare(start_date),
        end_date=date_to_tushare(end_date),
    )
    if moneyflow is not None:
        sections.append(_format_section(f"Money flow ({ts_code})", moneyflow, max_rows=20))

    top_list = _safe_call(
        "top_list",
        ts_code=ts_code,
        start_date=date_to_tushare(start_date),
        end_date=date_to_tushare(end_date),
    )
    if top_list is not None and not top_list.empty:
        sections.append(_format_section("Dragon-tiger list records", top_list, max_rows=20))

    if not sections:
        return "No money-flow data is available from the configured Tushare permissions."
    return "\n\n".join(sections)


def get_a_share_indicators(
    ts_code: str,
    trade_date: str,
    look_back_days: int = 120,
    indicators: list[str] | None = None,
) -> str:
    from stockstats import wrap

    ts_code = validate_ts_code(ts_code)
    indicators = indicators or ["close_20_sma", "close_60_sma", "macd", "rsi", "boll", "atr", "vr"]
    start = lookback_start(trade_date, max(look_back_days, 120))
    df = get_daily_frame(ts_code, start, trade_date)
    if df.empty:
        return f"No OHLCV rows available for {ts_code} before {trade_date}."

    rename = {
        "trade_date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
    }
    data = df.rename(columns=rename)
    data["date"] = pd.to_datetime(data["date"], format="%Y%m%d", errors="coerce")
    data = data.dropna(subset=["date", "close"]).sort_values("date")
    data["volume"] = pd.to_numeric(data.get("volume", 0), errors="coerce").fillna(0)
    stock = wrap(data[["date", "open", "high", "low", "close", "volume"]].copy())
    latest = stock.iloc[-1].copy()

    rows = []
    for ind in indicators:
        key = ind.strip().lower()
        if not key:
            continue
        try:
            stock[key]
            latest = stock.iloc[-1]
            value = latest.get(key, "")
            rows.append({"indicator": key, "latest_value": "" if pd.isna(value) else value})
        except Exception as exc:
            rows.append({"indicator": key, "latest_value": f"unsupported or unavailable: {exc}"})
    return _format_section(
        f"Technical indicators for {ts_code} through {trade_date}",
        pd.DataFrame(rows),
        max_rows=30,
    )


def get_company_profile(ts_code: str) -> str:
    ts_code = validate_ts_code(ts_code)
    basic = _call("stock_basic", ts_code=ts_code, fields="ts_code,symbol,name,area,industry,market,list_date")
    company = _safe_call("stock_company", ts_code=ts_code)
    sections = [_format_section("Company profile", basic)]
    if company is not None and not company.empty:
        sections.append(_format_section("Issuer details", company))
    return "\n\n".join(sections)


def get_financials(ts_code: str, report_type: str, period: str | None = None) -> str:
    ts_code = validate_ts_code(ts_code)
    report_type = (report_type or "").strip().lower()
    mapping = {
        "income": "income",
        "balancesheet": "balancesheet",
        "balance_sheet": "balancesheet",
        "cashflow": "cashflow",
        "cash_flow": "cashflow",
        "indicator": "fina_indicator",
        "fina_indicator": "fina_indicator",
    }
    if report_type not in mapping:
        return "report_type must be one of: income, balancesheet, cashflow, fina_indicator."
    kwargs = {"ts_code": ts_code}
    if period:
        kwargs["period"] = period.replace("-", "")
    df = _call(mapping[report_type], **kwargs)
    if "end_date" in df.columns:
        df = df.sort_values("end_date", ascending=False)
    return _format_section(f"{mapping[report_type]} for {ts_code}", df, max_rows=8)


def get_fundamental_snapshot(ts_code: str, curr_date: str) -> str:
    ts_code = validate_ts_code(ts_code)
    sections = [get_company_profile(ts_code)]
    for name in ["fina_indicator", "forecast", "express", "dividend", "share_float"]:
        df = _safe_call(name, ts_code=ts_code)
        if df is not None and not df.empty:
            sort_col = "ann_date" if "ann_date" in df.columns else df.columns[0]
            df = df.sort_values(sort_col, ascending=False)
            sections.append(_format_section(name, df, max_rows=6))
    return "\n\n".join(sections)


def get_announcements(
    ts_code: str,
    start_date: str,
    end_date: str,
    categories: list[str] | None = None,
) -> str:
    """Fetch announcements from Tushare first, with Cninfo as a public fallback."""
    ts_code = validate_ts_code(ts_code)
    tushare_note = ""
    try:
        df = _call(
            "anns_d",
            ts_code=ts_code,
            start_date=date_to_tushare(start_date),
            end_date=date_to_tushare(end_date),
        )
        if df is not None and not df.empty:
            if "ann_date" in df.columns:
                df = df.sort_values("ann_date", ascending=False)
            return _format_section(f"Tushare announcements for {ts_code}", df, max_rows=30)
        tushare_note = "Tushare anns_d returned no rows; falling back to Cninfo public query."
    except Exception as exc:
        tushare_note = (
            "Tushare anns_d is unavailable, likely because the separate announcement "
            f"permission is not enabled. Falling back to Cninfo public query. Error: {exc}"
        )

    from .cninfo_provider import get_cninfo_announcements

    fallback = get_cninfo_announcements(ts_code, start_date, end_date, categories)
    return f"## Announcement source fallback\n\n{tushare_note}\n\n{fallback}"


def get_return_series(ts_code: str, trade_date: str, holding_days: int) -> tuple[float | None, int | None]:
    start = trade_date
    end = lookback_start(trade_date, -holding_days - 14)
    df = get_daily_frame(ts_code, start, end)
    if len(df) < 2:
        return None, None
    actual_days = min(holding_days, len(df) - 1)
    close = pd.to_numeric(df["close"], errors="coerce")
    raw = float((close.iloc[actual_days] - close.iloc[0]) / close.iloc[0])
    return raw, actual_days
