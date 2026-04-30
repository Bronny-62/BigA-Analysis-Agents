"""Optional iFinD QuantAPI HTTP provider for A-share enrichment signals."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import pandas as pd

from .a_share_utils import dataframe_preview, validate_ts_code

logger = logging.getLogger(__name__)

IFIND_API_BASE = "https://quantapi.51ifind.com/api/v1"


@dataclass
class IFindError:
    endpoint: str
    message: str
    http_status: int | None = None
    error_code: Any = None
    raw: Any = None

    def log(self) -> None:
        logger.warning(
            "iFinD optional provider failed endpoint=%s http_status=%s error_code=%s message=%s",
            self.endpoint,
            self.http_status,
            self.error_code,
            self.message,
        )

    def markdown(self, title: str = "iFinD optional signal unavailable") -> str:
        rows = [
            {
                "endpoint": self.endpoint,
                "http_status": self.http_status if self.http_status is not None else "",
                "error_code": self.error_code if self.error_code is not None else "",
                "message": self.message,
            }
        ]
        return f"## {title}\n\n{dataframe_preview(pd.DataFrame(rows), max_rows=3)}"


def is_enabled() -> bool:
    value = os.getenv("IFIND_ENABLED", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def has_credentials() -> bool:
    return bool(os.getenv("IFIND_ACCESS_TOKEN") or os.getenv("IFIND_REFRESH_TOKEN"))


def status() -> str:
    rows = [
        {
            "enabled": is_enabled(),
            "api_base": os.getenv("IFIND_API_BASE", IFIND_API_BASE),
            "access_token": "configured" if os.getenv("IFIND_ACCESS_TOKEN") else "missing",
            "refresh_token": "configured" if os.getenv("IFIND_REFRESH_TOKEN") else "missing",
        }
    ]
    return f"## iFinD provider status\n\n{dataframe_preview(pd.DataFrame(rows), max_rows=3)}"


def optional_section(title: str, func, *args, **kwargs) -> str:
    if not is_enabled() or not has_credentials():
        return ""
    try:
        text = func(*args, **kwargs)
        return text
    except Exception as exc:
        error = _coerce_exception("optional", exc)
        error.log()
        return error.markdown(title)


def real_time_quote(ts_code: str, indicators: str | None = None) -> str:
    ts_code = validate_ts_code(ts_code)
    indicators = indicators or "latest,open,high,low,volume,amount,changeRatio"
    payload = {"codes": ts_code, "indicators": indicators}
    data, error = _post("real_time_quotation", payload)
    if error:
        error.log()
        return error.markdown("iFinD real-time quote unavailable")
    df = _payload_to_frame(data)
    if df.empty:
        error = IFindError("real_time_quotation", "iFinD returned no real-time quote rows.", raw=data)
        error.log()
        return error.markdown("iFinD real-time quote unavailable")
    return f"## iFinD real-time quote ({ts_code})\n\n{dataframe_preview(df, max_rows=8)}"


def history_quote(
    ts_code: str,
    start_date: str,
    end_date: str,
    indicators: str = "open,high,low,close,volume,amount,changeRatio",
) -> str:
    ts_code = validate_ts_code(ts_code)
    payload = {
        "codes": ts_code,
        "indicators": indicators,
        "startdate": start_date,
        "enddate": end_date,
        "functionpara": {"Fill": "Blank"},
    }
    data, error = _post("cmd_history_quotation", payload)
    if error:
        error.log()
        return error.markdown("iFinD history quote unavailable")
    df = _payload_to_frame(data)
    if df.empty:
        error = IFindError("cmd_history_quotation", "iFinD returned no history quote rows.", raw=data)
        error.log()
        return error.markdown("iFinD history quote unavailable")
    return f"## iFinD history quote ({ts_code})\n\n{dataframe_preview(df, max_rows=20)}"


def smart_stock_picking(searchstring: str, searchtype: str = "stock") -> str:
    payload = {"searchstring": searchstring, "searchtype": searchtype}
    data, error = _post("smart_stock_picking", payload)
    if error:
        error.log()
        return error.markdown("iFinD smart stock picking unavailable")
    df = _payload_to_frame(data)
    if df.empty:
        error = IFindError("smart_stock_picking", "iFinD returned no smart-picking rows.", raw=data)
        error.log()
        return error.markdown("iFinD smart stock picking unavailable")
    return f"## iFinD smart stock picking: {searchstring}\n\n{dataframe_preview(df, max_rows=20)}"


def popularity_signal(ts_code: str, trade_date: str | None = None) -> str:
    ts_code = validate_ts_code(ts_code)
    query = f"{ts_code} 同花顺人气 人气排名 人气分位"
    if trade_date:
        query += f" {trade_date}"
    return smart_stock_picking(query, "stock")


def refresh_access_token() -> tuple[str | None, IFindError | None]:
    refresh_token = os.getenv("IFIND_REFRESH_TOKEN")
    if not refresh_token:
        return None, IFindError("get_access_token", "IFIND_REFRESH_TOKEN is not configured.")
    base_url = os.getenv("IFIND_API_BASE", IFIND_API_BASE).rstrip("/")
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                f"{base_url}/get_access_token",
                headers={"Content-Type": "application/json", "refresh_token": refresh_token},
            )
        payload = _safe_json(response)
        if response.status_code >= 400:
            return None, IFindError(
                "get_access_token",
                _error_message(payload) or response.text[:300],
                response.status_code,
                _error_code(payload),
                payload,
            )
        token = ((payload or {}).get("data") or {}).get("access_token")
        if not token:
            return None, IFindError("get_access_token", "No access_token in iFinD response.", response.status_code, _error_code(payload), payload)
        return token, None
    except Exception as exc:
        return None, IFindError("get_access_token", str(exc))


@lru_cache(maxsize=1)
def _access_token() -> tuple[str | None, IFindError | None]:
    token = os.getenv("IFIND_ACCESS_TOKEN")
    if token:
        return token, None
    return refresh_access_token()


def _post(endpoint: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, IFindError | None]:
    if not is_enabled():
        return None, IFindError(endpoint, "iFinD provider is disabled by IFIND_ENABLED=false.")
    if not has_credentials():
        return None, IFindError(endpoint, "No iFinD token configured. Set IFIND_ACCESS_TOKEN or IFIND_REFRESH_TOKEN in .env.")
    token, token_error = _access_token()
    if token_error:
        return None, token_error
    base_url = os.getenv("IFIND_API_BASE", IFIND_API_BASE).rstrip("/")
    try:
        with httpx.Client(timeout=float(os.getenv("IFIND_TIMEOUT_SECONDS", "20"))) as client:
            response = client.post(
                f"{base_url}/{endpoint}",
                headers={"Content-Type": "application/json", "access_token": token or ""},
                json=payload,
            )
        data = _safe_json(response)
        if response.status_code in {401, 403} and os.getenv("IFIND_REFRESH_TOKEN"):
            _access_token.cache_clear()
            refreshed, refresh_error = refresh_access_token()
            if refresh_error:
                return None, refresh_error
            with httpx.Client(timeout=float(os.getenv("IFIND_TIMEOUT_SECONDS", "20"))) as client:
                response = client.post(
                    f"{base_url}/{endpoint}",
                    headers={"Content-Type": "application/json", "access_token": refreshed or ""},
                    json=payload,
                )
            data = _safe_json(response)
        if response.status_code >= 400:
            return None, IFindError(endpoint, _error_message(data) or response.text[:300], response.status_code, _error_code(data), data)
        error_code = _error_code(data)
        if error_code not in (None, 0, "0"):
            return None, IFindError(endpoint, _error_message(data) or "iFinD returned non-zero error code.", response.status_code, error_code, data)
        return data, None
    except Exception as exc:
        return None, IFindError(endpoint, str(exc))


def _payload_to_frame(payload: Any) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        nested = payload["data"]
        if "tables" in nested or isinstance(nested.get("data"), (list, dict)):
            return _payload_to_frame(nested)
        if any(isinstance(value, list) for value in nested.values()):
            return pd.DataFrame(_dict_table_to_rows(nested))
        return pd.json_normalize(nested)
    if isinstance(payload, dict) and isinstance(payload.get("tables"), list):
        rows = []
        for table in payload["tables"]:
            if not isinstance(table, dict):
                continue
            code = table.get("thscode") or table.get("code")
            table_data = table.get("table") or table.get("data") or {}
            if isinstance(table_data, dict):
                rows.extend(_dict_table_to_rows(table_data, code))
            elif isinstance(table_data, list):
                for item in table_data:
                    if isinstance(item, dict):
                        row = {"thscode": code} if code else {}
                        row.update(item)
                        rows.append(row)
        return pd.DataFrame(rows)
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return pd.DataFrame(payload["data"])
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        return pd.json_normalize(payload)
    return pd.DataFrame()


def _dict_table_to_rows(table_data: dict[str, Any], code: str | None = None) -> list[dict[str, Any]]:
    list_lengths = [len(value) for value in table_data.values() if isinstance(value, list)]
    if not list_lengths:
        row = {"thscode": code} if code else {}
        row.update(table_data)
        return [row]
    n = max(list_lengths)
    rows = []
    for idx in range(n):
        row = {"thscode": code} if code else {}
        for key, value in table_data.items():
            row[key] = value[idx] if isinstance(value, list) and idx < len(value) else value
        rows.append(row)
    return rows


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return None


def _error_code(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in ("errorcode", "error_code", "code", "status"):
            if key in payload:
                return payload[key]
    return None


def _error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("errmsg", "error_description", "message", "msg", "error"):
            if payload.get(key):
                return str(payload[key])
    return ""


def _coerce_exception(endpoint: str, exc: Exception) -> IFindError:
    if isinstance(exc, IFindRuntimeError):
        return exc.error
    return IFindError(endpoint, str(exc))


class IFindRuntimeError(RuntimeError):
    def __init__(self, error: IFindError):
        super().__init__(error.message)
        self.error = error
