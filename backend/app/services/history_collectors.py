from __future__ import annotations

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.schemas import BrowserName, HistoryEvent
from backend.app.services.privacy import domain_from_url, redact_text, sanitize_url


CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
SAFARI_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
WINDOW_SYNC_LIMIT = 10000
FULL_SYNC_LIMIT = 250000

HOME = Path.home()
CHROME_ROOT = HOME / "Library/Application Support/Google/Chrome"
BRAVE_ROOT = HOME / "Library/Application Support/BraveSoftware/Brave-Browser"
SAFARI_HISTORY_PATH = HOME / "Library/Safari/History.db"


@dataclass(frozen=True)
class BrowserScanResult:
    browser: str
    events: list[HistoryEvent]
    scanned_rows: int
    error: str | None = None


@dataclass(frozen=True)
class BrowserSource:
    browser: BrowserName
    label: str
    db_path: Path



def _copy_to_temp(db_path: Path) -> tuple[Path, list[Path]]:
    with tempfile.NamedTemporaryFile(prefix="wave_history_", suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    shutil.copy2(db_path, tmp_path)

    sidecars: list[Path] = []
    for suffix in ("-wal", "-shm"):
        src = Path(f"{db_path}{suffix}")
        if not src.exists():
            continue
        dst = Path(f"{tmp_path}{suffix}")
        try:
            shutil.copy2(src, dst)
            sidecars.append(dst)
        except FileNotFoundError:
            # Browser may rotate/remove sidecar between existence check and copy.
            continue

    return tmp_path, sidecars



def _run_sqlite_query(db_path: Path, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    temp_path, sidecars = _copy_to_temp(db_path)
    try:
        conn = sqlite3.connect(temp_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return rows
    finally:
        temp_path.unlink(missing_ok=True)
        for sidecar in sidecars:
            sidecar.unlink(missing_ok=True)



def _to_local_naive(dt_utc: datetime) -> datetime:
    return dt_utc.astimezone().replace(tzinfo=None)



def _is_in_capture_window(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour



def _profile_sort_key(name: str) -> tuple[int, int, str]:
    if name == "Default":
        return (0, 0, name)
    if name.startswith("Profile "):
        suffix = name.removeprefix("Profile ").strip()
        if suffix.isdigit():
            return (1, int(suffix), name)
    return (2, 0, name)



def _discover_chromium_history_paths(root: Path) -> list[tuple[str, Path]]:
    if not root.exists():
        return []

    discovered: list[tuple[str, Path]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name == "Default" or child.name.startswith("Profile "):
            history_path = child / "History"
            if history_path.exists():
                discovered.append((child.name, history_path))

    discovered.sort(key=lambda item: _profile_sort_key(item[0]))
    return discovered



def _permission_error(exc: Exception) -> tuple[str, str]:
    text = str(exc)
    lowered = text.lower()
    if "operation not permitted" in lowered or "permission denied" in lowered:
        return (
            "permission_required",
            "Grant Full Disk Access to your terminal/Python in macOS Privacy & Security.",
        )
    if "database is locked" in lowered:
        return (
            "error",
            "Browser history database is locked. Close that browser and try again.",
        )
    return "error", "Unable to access browser history database."



def _browser_roots() -> dict[BrowserName, Path]:
    return {
        "chrome": CHROME_ROOT,
        "brave": BRAVE_ROOT,
        "safari": SAFARI_HISTORY_PATH,
    }



def _selected_sources(browsers: list[BrowserName]) -> list[BrowserSource]:
    sources: list[BrowserSource] = []
    for browser in browsers:
        if browser == "safari":
            sources.append(BrowserSource(browser="safari", label="safari", db_path=SAFARI_HISTORY_PATH))
            continue

        root = CHROME_ROOT if browser == "chrome" else BRAVE_ROOT
        profiles = _discover_chromium_history_paths(root)
        if not profiles:
            fallback = root / "Default/History"
            sources.append(BrowserSource(browser=browser, label=browser, db_path=fallback))
            continue

        multiple_profiles = len(profiles) > 1
        for profile_name, history_path in profiles:
            label = browser if not multiple_profiles and profile_name == "Default" else f"{browser}:{profile_name}"
            sources.append(BrowserSource(browser=browser, label=label, db_path=history_path))

    return sources



def collect_permission_status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for browser in ["chrome", "brave", "safari"]:
        if browser == "safari":
            db_path = SAFARI_HISTORY_PATH
            if not db_path.exists():
                rows.append(
                    {
                        "browser": browser,
                        "path": str(db_path),
                        "exists": False,
                        "readable": False,
                        "status": "missing",
                        "message": "History database not found.",
                    }
                )
                continue

            try:
                _run_sqlite_query(db_path, "SELECT 1")
            except Exception as exc:  # pragma: no cover - filesystem/permission variance
                status, message = _permission_error(exc)
                rows.append(
                    {
                        "browser": browser,
                        "path": str(db_path),
                        "exists": True,
                        "readable": False,
                        "status": status,
                        "message": message,
                    }
                )
                continue

            rows.append(
                {
                    "browser": browser,
                    "path": str(db_path),
                    "exists": True,
                    "readable": True,
                    "status": "ready",
                    "message": "History database is accessible.",
                }
            )
            continue

        root = CHROME_ROOT if browser == "chrome" else BRAVE_ROOT
        profile_paths = _discover_chromium_history_paths(root)
        if not profile_paths:
            fallback = root / "Default/History"
            rows.append(
                {
                    "browser": browser,
                    "path": str(fallback),
                    "exists": False,
                    "readable": False,
                    "status": "missing",
                    "message": "No browser profiles with history were found.",
                }
            )
            continue

        readable_profiles = 0
        latest_status = "error"
        latest_message = "Unable to access browser history database."

        for _, db_path in profile_paths:
            try:
                _run_sqlite_query(db_path, "SELECT 1")
                readable_profiles += 1
            except Exception as exc:  # pragma: no cover - filesystem/permission variance
                latest_status, latest_message = _permission_error(exc)

        if readable_profiles == 0:
            rows.append(
                {
                    "browser": browser,
                    "path": str(root),
                    "exists": True,
                    "readable": False,
                    "status": latest_status,
                    "message": latest_message,
                }
            )
            continue

        rows.append(
            {
                "browser": browser,
                "path": str(root),
                "exists": True,
                "readable": True,
                "status": "ready",
                "message": f"{readable_profiles}/{len(profile_paths)} profile history databases are accessible.",
            }
        )
    return rows



def _collect_chromium_history(
    browser_label: str, db_path: Path, lookback_hours: int, include_all_history: bool
) -> BrowserScanResult:
    if not db_path.exists():
        return BrowserScanResult(browser=browser_label, events=[], scanned_rows=0, error="history file not found")

    if include_all_history:
        query = f"""
            SELECT urls.url AS url, COALESCE(urls.title, '') AS title, visits.visit_time AS visit_time
            FROM visits
            JOIN urls ON visits.url = urls.id
            ORDER BY visits.visit_time DESC
            LIMIT {FULL_SYNC_LIMIT}
        """
        params: tuple = ()
    else:
        threshold = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        min_ts = int((threshold - CHROME_EPOCH).total_seconds() * 1_000_000)
        query = f"""
            SELECT urls.url AS url, COALESCE(urls.title, '') AS title, visits.visit_time AS visit_time
            FROM visits
            JOIN urls ON visits.url = urls.id
            WHERE visits.visit_time >= ?
            ORDER BY visits.visit_time DESC
            LIMIT {WINDOW_SYNC_LIMIT}
        """
        params = (min_ts,)

    try:
        rows = _run_sqlite_query(db_path, query, params)
    except Exception as exc:  # pragma: no cover - filesystem/permission variance
        _, message = _permission_error(exc)
        return BrowserScanResult(browser=browser_label, events=[], scanned_rows=0, error=message)

    events: list[HistoryEvent] = []
    for row in rows:
        raw_url = row["url"] or ""
        safe_url = sanitize_url(raw_url)
        if not safe_url.startswith(("http://", "https://")):
            continue

        visited_utc = CHROME_EPOCH + timedelta(microseconds=int(row["visit_time"]))
        safe_title = redact_text((row["title"] or "Untitled").strip() or "Untitled", max_len=240)

        events.append(
            HistoryEvent(
                browser=browser_label,
                url=safe_url,
                title=safe_title,
                domain=domain_from_url(safe_url),
                visited_at=_to_local_naive(visited_utc),
                visit_count=1,
            )
        )

    return BrowserScanResult(browser=browser_label, events=events, scanned_rows=len(rows), error=None)



def _collect_safari_history(browser_label: str, db_path: Path, lookback_hours: int, include_all_history: bool) -> BrowserScanResult:
    if not db_path.exists():
        return BrowserScanResult(browser=browser_label, events=[], scanned_rows=0, error="history file not found")

    if include_all_history:
        query = f"""
            SELECT hi.url AS url, COALESCE(hv.title, '') AS title, hv.visit_time AS visit_time
            FROM history_visits hv
            JOIN history_items hi ON hv.history_item = hi.id
            ORDER BY hv.visit_time DESC
            LIMIT {FULL_SYNC_LIMIT}
        """
        params: tuple = ()
    else:
        threshold = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        min_ts = int((threshold - SAFARI_EPOCH).total_seconds())
        query = f"""
            SELECT hi.url AS url, COALESCE(hv.title, '') AS title, hv.visit_time AS visit_time
            FROM history_visits hv
            JOIN history_items hi ON hv.history_item = hi.id
            WHERE hv.visit_time >= ?
            ORDER BY hv.visit_time DESC
            LIMIT {WINDOW_SYNC_LIMIT}
        """
        params = (min_ts,)

    try:
        rows = _run_sqlite_query(db_path, query, params)
    except Exception as exc:  # pragma: no cover - filesystem/permission variance
        _, message = _permission_error(exc)
        return BrowserScanResult(browser=browser_label, events=[], scanned_rows=0, error=message)

    events: list[HistoryEvent] = []
    for row in rows:
        raw_url = row["url"] or ""
        safe_url = sanitize_url(raw_url)
        if not safe_url.startswith(("http://", "https://")):
            continue

        visited_utc = SAFARI_EPOCH + timedelta(seconds=float(row["visit_time"]))
        safe_title = redact_text((row["title"] or "Untitled").strip() or "Untitled", max_len=240)

        events.append(
            HistoryEvent(
                browser=browser_label,
                url=safe_url,
                title=safe_title,
                domain=domain_from_url(safe_url),
                visited_at=_to_local_naive(visited_utc),
                visit_count=1,
            )
        )

    return BrowserScanResult(browser=browser_label, events=events, scanned_rows=len(rows), error=None)



def collect_history(
    lookback_hours: int = 24,
    include_all_history: bool = False,
    browsers: list[BrowserName] | None = None,
    capture_start_hour: int | None = None,
    capture_end_hour: int | None = None,
) -> tuple[list[HistoryEvent], dict[str, int], dict[str, str], int]:
    selected_browsers = browsers or ["chrome", "brave", "safari"]
    sources = _selected_sources(selected_browsers)

    results: list[BrowserScanResult] = []
    for source in sources:
        if source.browser == "safari":
            results.append(
                _collect_safari_history(source.label, source.db_path, lookback_hours, include_all_history)
            )
        else:
            results.append(
                _collect_chromium_history(source.label, source.db_path, lookback_hours, include_all_history)
            )

    all_events: list[HistoryEvent] = []
    by_browser: dict[str, int] = {}
    errors: dict[str, str] = {}
    scanned = 0

    for result in results:
        scanned += result.scanned_rows
        all_events.extend(result.events)
        by_browser[result.browser] = len(result.events)
        if result.error:
            errors[result.browser] = result.error

    if capture_start_hour is not None and capture_end_hour is not None:
        filtered: list[HistoryEvent] = []
        filtered_counts = {browser: 0 for browser in by_browser}
        for event in all_events:
            if _is_in_capture_window(event.visited_at.hour, capture_start_hour, capture_end_hour):
                filtered.append(event)
                filtered_counts[event.browser] = filtered_counts.get(event.browser, 0) + 1
        all_events = filtered
        by_browser = filtered_counts

    all_events.sort(key=lambda event: event.visited_at, reverse=True)
    return all_events, by_browser, errors, scanned



def _exec_if_exists(conn: sqlite3.Connection, statement: str) -> None:
    try:
        conn.execute(statement)
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "no such table" in message:
            return
        raise



def _clear_chromium_history(db_path: Path) -> tuple[int, str | None]:
    if not db_path.exists():
        return 0, "history file not found"

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        conn.row_factory = sqlite3.Row
        visit_row = conn.execute("SELECT COUNT(*) AS total FROM visits").fetchone()
        deleted = int(visit_row["total"]) if visit_row else 0

        conn.execute("BEGIN IMMEDIATE")
        _exec_if_exists(conn, "DELETE FROM visit_source")
        _exec_if_exists(conn, "DELETE FROM keyword_search_terms")
        _exec_if_exists(conn, "DELETE FROM segment_usage")
        _exec_if_exists(conn, "DELETE FROM segments")
        _exec_if_exists(conn, "DELETE FROM visits")
        _exec_if_exists(conn, "DELETE FROM urls")
        conn.commit()
        return deleted, None
    except Exception as exc:  # pragma: no cover - filesystem/permission variance
        if conn is not None:
            conn.rollback()
        _, message = _permission_error(exc)
        return 0, message
    finally:
        if conn is not None:
            conn.close()



def _clear_safari_history(db_path: Path) -> tuple[int, str | None]:
    if not db_path.exists():
        return 0, "history file not found"

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        conn.row_factory = sqlite3.Row
        visits_row = conn.execute("SELECT COUNT(*) AS total FROM history_visits").fetchone()
        deleted = int(visits_row["total"]) if visits_row else 0

        conn.execute("BEGIN IMMEDIATE")
        _exec_if_exists(conn, "DELETE FROM history_visits")
        _exec_if_exists(conn, "DELETE FROM history_items")
        _exec_if_exists(conn, "DELETE FROM history_tombstones")
        conn.commit()
        return deleted, None
    except Exception as exc:  # pragma: no cover - filesystem/permission variance
        if conn is not None:
            conn.rollback()
        _, message = _permission_error(exc)
        return 0, message
    finally:
        if conn is not None:
            conn.close()



def clear_browser_history(browsers: list[BrowserName] | None = None) -> tuple[dict[str, int], dict[str, str]]:
    selected_browsers = browsers or ["chrome", "brave", "safari"]
    deleted: dict[str, int] = {}
    errors: dict[str, str] = {}

    for browser in selected_browsers:
        if browser == "safari":
            count, error = _clear_safari_history(SAFARI_HISTORY_PATH)
            if error:
                errors["safari"] = error
            else:
                deleted["safari"] = count
            continue

        root = CHROME_ROOT if browser == "chrome" else BRAVE_ROOT
        profiles = _discover_chromium_history_paths(root)
        if not profiles:
            errors[browser] = "No browser profiles with history were found."
            continue

        multiple_profiles = len(profiles) > 1
        for profile_name, db_path in profiles:
            label = browser if not multiple_profiles and profile_name == "Default" else f"{browser}:{profile_name}"
            count, error = _clear_chromium_history(db_path)
            if error:
                errors[label] = error
            else:
                deleted[label] = count

    return deleted, errors
