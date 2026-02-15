from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from backend.app.schemas import HistoryEvent
from backend.app.services.privacy import domain_from_url, redact_text, sanitize_url


class WaveStorage:
    PRIVACY_SCHEMA_VERSION = "3"

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS history_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    browser TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    visited_at TEXT NOT NULL,
                    visit_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(browser, url, visited_at)
                );

                CREATE INDEX IF NOT EXISTS idx_history_visited_at ON history_events(visited_at);
                CREATE INDEX IF NOT EXISTS idx_history_domain ON history_events(domain);

                CREATE TABLE IF NOT EXISTS daily_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL,
                    model TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    highlights TEXT NOT NULL,
                    risk_flags TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    reasoning_trace TEXT NOT NULL DEFAULT '',
                    source_events INTEGER NOT NULL,
                    generated_at TEXT NOT NULL,
                    UNIQUE(report_date)
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            columns = conn.execute("PRAGMA table_info(daily_reports)").fetchall()
            column_names = {row["name"] for row in columns}
            if "reasoning_trace" not in column_names:
                conn.execute(
                    "ALTER TABLE daily_reports ADD COLUMN reasoning_trace TEXT NOT NULL DEFAULT ''"
                )
            if "details_json" not in column_names:
                conn.execute(
                    "ALTER TABLE daily_reports ADD COLUMN details_json TEXT NOT NULL DEFAULT '{}'"
                )

            self._run_privacy_migration(conn)

    def _run_privacy_migration(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT value FROM app_meta WHERE key = 'privacy_schema_version'").fetchone()
        if row and row["value"] == self.PRIVACY_SCHEMA_VERSION:
            return

        self._sanitize_existing_events(conn)
        conn.execute("DELETE FROM daily_reports")
        conn.execute(
            """
            INSERT INTO app_meta(key, value) VALUES ('privacy_schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (self.PRIVACY_SCHEMA_VERSION,),
        )

    def _sanitize_existing_events(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT id, url, title, domain FROM history_events ORDER BY id ASC"
        ).fetchall()
        for row in rows:
            safe_url = sanitize_url(row["url"])
            if not safe_url.startswith(("http://", "https://")):
                conn.execute("DELETE FROM history_events WHERE id = ?", (row["id"],))
                continue
            safe_title = redact_text(row["title"], max_len=240) or "Untitled"
            safe_domain = domain_from_url(safe_url)

            if safe_url == row["url"] and safe_title == row["title"] and safe_domain == row["domain"]:
                continue

            try:
                conn.execute(
                    """
                    UPDATE history_events
                    SET url = ?, title = ?, domain = ?
                    WHERE id = ?
                    """,
                    (safe_url, safe_title, safe_domain, row["id"]),
                )
            except sqlite3.IntegrityError:
                conn.execute("DELETE FROM history_events WHERE id = ?", (row["id"],))

    def insert_events(self, events: list[HistoryEvent]) -> int:
        if not events:
            return 0

        rows: list[tuple[str, str, str, str, str, int]] = []
        for event in events:
            safe_url = sanitize_url(event.url)
            if not safe_url.startswith(("http://", "https://")):
                continue
            safe_title = redact_text(event.title, max_len=240) or "Untitled"
            safe_domain = domain_from_url(safe_url)
            rows.append(
                (
                    event.browser,
                    safe_url,
                    safe_title,
                    safe_domain,
                    event.visited_at.isoformat(),
                    event.visit_count,
                )
            )

        if not rows:
            return 0

        with self._connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT OR IGNORE INTO history_events (
                    browser, url, title, domain, visited_at, visit_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            inserted = conn.total_changes - before
        return inserted

    def list_events_by_date(self, target_date: date, limit: int = 500) -> list[HistoryEvent]:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        with self._connect() as conn:
            result = conn.execute(
                """
                SELECT browser, url, title, domain, visited_at, visit_count
                FROM history_events
                WHERE visited_at BETWEEN ? AND ?
                ORDER BY visited_at DESC
                LIMIT ?
                """,
                (start.isoformat(), end.isoformat(), limit),
            ).fetchall()

        events: list[HistoryEvent] = []
        for row in result:
            events.append(
                HistoryEvent(
                    browser=row["browser"],
                    url=row["url"],
                    title=row["title"],
                    domain=row["domain"],
                    visited_at=datetime.fromisoformat(row["visited_at"]),
                    visit_count=row["visit_count"],
                )
            )
        return events

    def top_domains_by_date(self, target_date: date, limit: int = 8) -> list[dict[str, int | str]]:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, COUNT(*) AS total
                FROM history_events
                WHERE visited_at BETWEEN ? AND ?
                GROUP BY domain
                ORDER BY total DESC
                LIMIT ?
                """,
                (start.isoformat(), end.isoformat(), limit),
            ).fetchall()

        return [{"domain": r["domain"], "count": int(r["total"])} for r in rows]

    def save_daily_report(
        self,
        *,
        report_date: date,
        model: str,
        summary: str,
        highlights: list[str],
        risk_flags: list[str],
        details: dict[str, object] | None,
        reasoning_trace: str | None,
        source_events: int,
        generated_at: datetime,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_reports (
                    report_date, model, summary, highlights, risk_flags, details_json, reasoning_trace, source_events, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    model=excluded.model,
                    summary=excluded.summary,
                    highlights=excluded.highlights,
                    risk_flags=excluded.risk_flags,
                    details_json=excluded.details_json,
                    reasoning_trace=excluded.reasoning_trace,
                    source_events=excluded.source_events,
                    generated_at=excluded.generated_at
                """,
                (
                    report_date.isoformat(),
                    model,
                    summary,
                    json.dumps(highlights),
                    json.dumps(risk_flags),
                    json.dumps(details or {}),
                    reasoning_trace or "",
                    source_events,
                    generated_at.isoformat(),
                ),
            )

    def get_daily_report(self, report_date: date) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT report_date, model, summary, highlights, risk_flags, details_json, reasoning_trace, source_events, generated_at
                FROM daily_reports
                WHERE report_date = ?
                """,
                (report_date.isoformat(),),
            ).fetchone()

        if not row:
            return None

        return {
            "date": row["report_date"],
            "model": row["model"],
            "summary": row["summary"],
            "highlights": json.loads(row["highlights"]),
            "risk_flags": json.loads(row["risk_flags"]),
            "details": json.loads(row["details_json"] or "{}"),
            "reasoning_trace": row["reasoning_trace"] or None,
            "source_events": row["source_events"],
            "generated_at": row["generated_at"],
        }

    def count_events_by_date(self, target_date: date) -> int:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        with self._connect() as conn:
            value = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM history_events
                WHERE visited_at BETWEEN ? AND ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchone()
        return int(value["total"]) if value else 0

    def latest_event_date(self) -> date | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(visited_at) AS max_ts
                FROM history_events
                """
            ).fetchone()
        if not row or not row["max_ts"]:
            return None
        return datetime.fromisoformat(row["max_ts"]).date()

    def search_events(self, query: str, limit: int = 30) -> tuple[list[HistoryEvent], int]:
        q = f"%{query.strip().lower()}%"
        if not query.strip():
            return [], 0

        with self._connect() as conn:
            total_row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM history_events
                WHERE lower(title) LIKE ?
                   OR lower(url) LIKE ?
                   OR lower(domain) LIKE ?
                """,
                (q, q, q),
            ).fetchone()

            rows = conn.execute(
                """
                SELECT browser, url, title, domain, visited_at, visit_count
                FROM history_events
                WHERE lower(title) LIKE ?
                   OR lower(url) LIKE ?
                   OR lower(domain) LIKE ?
                ORDER BY visited_at DESC
                LIMIT ?
                """,
                (q, q, q, limit),
            ).fetchall()

        events = [
            HistoryEvent(
                browser=row["browser"],
                url=row["url"],
                title=row["title"],
                domain=row["domain"],
                visited_at=datetime.fromisoformat(row["visited_at"]),
                visit_count=row["visit_count"],
            )
            for row in rows
        ]
        total = int(total_row["total"]) if total_row else 0
        return events, total

    def similar_events_by_domains(self, domains: list[str], exclude_urls: set[str], limit: int = 20) -> list[HistoryEvent]:
        clean_domains = [d for d in domains if d]
        if not clean_domains:
            return []

        placeholders = ",".join(["?"] * len(clean_domains))
        params: list[str | int] = list(clean_domains)

        exclusion_sql = ""
        if exclude_urls:
            url_placeholders = ",".join(["?"] * len(exclude_urls))
            exclusion_sql = f" AND url NOT IN ({url_placeholders})"
            params.extend(list(exclude_urls))

        params.append(limit)
        sql = f"""
            SELECT browser, url, title, domain, visited_at, visit_count
            FROM history_events
            WHERE domain IN ({placeholders})
            {exclusion_sql}
            ORDER BY visited_at DESC
            LIMIT ?
        """

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        return [
            HistoryEvent(
                browser=row["browser"],
                url=row["url"],
                title=row["title"],
                domain=row["domain"],
                visited_at=datetime.fromisoformat(row["visited_at"]),
                visit_count=row["visit_count"],
            )
            for row in rows
        ]

    def clear_history(self, include_reports: bool = True) -> tuple[int, int]:
        with self._connect() as conn:
            events_row = conn.execute("SELECT COUNT(*) AS total FROM history_events").fetchone()
            deleted_events = int(events_row["total"]) if events_row else 0
            conn.execute("DELETE FROM history_events")

            deleted_reports = 0
            if include_reports:
                reports_row = conn.execute("SELECT COUNT(*) AS total FROM daily_reports").fetchone()
                deleted_reports = int(reports_row["total"]) if reports_row else 0
                conn.execute("DELETE FROM daily_reports")

        return deleted_events, deleted_reports

    def delete_events_by_capture_window(
        self, target_date: date, capture_start_hour: int, capture_end_hour: int
    ) -> int:
        target = target_date.isoformat()
        hour_expr = "CAST(substr(visited_at, 12, 2) AS INTEGER)"

        with self._connect() as conn:
            before = conn.total_changes
            if capture_start_hour == capture_end_hour:
                conn.execute(
                    """
                    DELETE FROM history_events
                    WHERE substr(visited_at, 1, 10) = ?
                    """,
                    (target,),
                )
            elif capture_start_hour < capture_end_hour:
                conn.execute(
                    f"""
                    DELETE FROM history_events
                    WHERE substr(visited_at, 1, 10) = ?
                      AND {hour_expr} >= ?
                      AND {hour_expr} < ?
                    """,
                    (target, capture_start_hour, capture_end_hour),
                )
            else:
                conn.execute(
                    f"""
                    DELETE FROM history_events
                    WHERE substr(visited_at, 1, 10) = ?
                      AND ({hour_expr} >= ? OR {hour_expr} < ?)
                    """,
                    (target, capture_start_hour, capture_end_hour),
                )

            return conn.total_changes - before
