"""SQLite storage for authorized social monitor captures."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingagents.dataflows.a_share_utils import cache_dir, validate_ts_code


class SocialMonitorStorage:
    def __init__(self, path: Path | None = None):
        self.path = path or cache_dir("social_monitor") / "posts.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def insert_posts(self, posts: list[dict[str, Any]]) -> int:
        inserted = 0
        with self._connect() as conn:
            for post in posts:
                columns = _POST_COLUMNS
                values = [_serialize(post.get(col)) for col in columns]
                cursor = conn.execute(
                    f"""
                    INSERT OR IGNORE INTO social_posts ({", ".join(columns)})
                    VALUES ({", ".join("?" for _ in columns)})
                    """,
                    values,
                )
                inserted += cursor.rowcount
        return inserted

    def begin_run(self, source: str, ts_code: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO social_runs (source, ts_code, status, started_at) VALUES (?, ?, ?, ?)",
                (source, ts_code, "running", now),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, posts_seen: int, posts_inserted: int, error: str = "") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE social_runs
                SET status = ?, posts_seen = ?, posts_inserted = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, posts_seen, posts_inserted, error, now, run_id),
            )

    def query_posts(self, ts_code: str, start_date: str, end_date: str, limit: int = 50) -> list[dict[str, Any]]:
        ts_code = validate_ts_code(ts_code)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM social_posts
                WHERE ts_code = ?
                  AND substr(coalesce(created_at, captured_at, ''), 1, 10) BETWEEN ? AND ?
                ORDER BY hotness_score DESC, captured_at DESC
                LIMIT ?
                """,
                (ts_code, start_date, end_date, limit),
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def summaries(self, ts_code: str) -> list[dict[str, Any]]:
        ts_code = validate_ts_code(ts_code)
        with self._connect() as conn:
            post_rows = conn.execute(
                """
                SELECT source, COUNT(*) AS post_count, MAX(captured_at) AS last_captured_at
                FROM social_posts WHERE ts_code = ? GROUP BY source
                """,
                (ts_code,),
            ).fetchall()
            run_rows = conn.execute(
                """
                SELECT source, status, posts_seen, posts_inserted, error, started_at, finished_at
                FROM social_runs WHERE ts_code = ?
                ORDER BY started_at DESC
                """,
                (ts_code,),
            ).fetchall()
        summaries = [_row_to_dict(row) for row in post_rows]
        summaries.extend(_row_to_dict(row) for row in run_rows)
        return summaries

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS social_posts (
                    source TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    platform_symbol TEXT,
                    post_id TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    author TEXT,
                    author_id TEXT,
                    created_at TEXT,
                    captured_at TEXT,
                    reply_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    read_count INTEGER DEFAULT 0,
                    repost_count INTEGER DEFAULT 0,
                    url TEXT,
                    text_signature TEXT,
                    sentiment TEXT,
                    sentiment_score REAL DEFAULT 0,
                    hotness_score REAL DEFAULT 0,
                    confidence TEXT,
                    raw_json TEXT,
                    UNIQUE(source, ts_code, post_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS social_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    status TEXT,
                    posts_seen INTEGER DEFAULT 0,
                    posts_inserted INTEGER DEFAULT 0,
                    error TEXT,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )


def query_social_posts(ts_code: str, start_date: str, end_date: str, limit: int = 50) -> list[dict[str, Any]]:
    return SocialMonitorStorage().query_posts(ts_code, start_date, end_date, limit)


def get_social_monitor_summary(ts_code: str) -> list[dict[str, Any]]:
    return SocialMonitorStorage().summaries(ts_code)


_POST_COLUMNS = [
    "source",
    "ts_code",
    "platform_symbol",
    "post_id",
    "title",
    "content",
    "author",
    "author_id",
    "created_at",
    "captured_at",
    "reply_count",
    "like_count",
    "read_count",
    "repost_count",
    "url",
    "text_signature",
    "sentiment",
    "sentiment_score",
    "hotness_score",
    "confidence",
    "raw_json",
]


def _serialize(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)

