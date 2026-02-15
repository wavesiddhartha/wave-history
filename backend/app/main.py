from __future__ import annotations

import ipaddress
import logging
from datetime import date, datetime
from hmac import compare_digest
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.db.storage import WaveStorage
from backend.app.schemas import (
    ClearHistoryRequest,
    ClearHistoryResponse,
    DailySnapshot,
    DeleteWindowRequest,
    DeleteWindowResponse,
    PermissionStatusResponse,
    ReportRequest,
    ReportResponse,
    SearchResponse,
    SyncRequest,
    SyncResult,
)
from backend.app.services.ai_client import generate_daily_report
from backend.app.services.history_collectors import (
    clear_browser_history,
    collect_history,
    collect_permission_status,
)
from backend.app.services.report_pdf import build_report_pdf


logger = logging.getLogger(__name__)

app = FastAPI(title="Wave", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Wave-Token"],
)

storage = WaveStorage(settings.wave_db_path)

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend"
STATIC_ROOT = FRONTEND_ROOT / "static"
INDEX_TEMPLATE = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")



def _is_loopback_host(host: str) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False



def require_api_access(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Forbidden")

    provided_token = request.headers.get("X-Wave-Token", "")
    if not provided_token or not compare_digest(provided_token, settings.api_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/")
def index() -> HTMLResponse:
    html = INDEX_TEMPLATE.replace("__WAVE_API_TOKEN_VALUE__", settings.api_token)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sync", response_model=SyncResult)
def sync_history(payload: SyncRequest, _: None = Depends(require_api_access)) -> SyncResult:
    events, by_browser, errors, scanned = collect_history(
        lookback_hours=payload.lookback_hours,
        include_all_history=payload.include_all_history,
        browsers=payload.browsers,
        capture_start_hour=payload.capture_start_hour,
        capture_end_hour=payload.capture_end_hour,
    )
    inserted = storage.insert_events(events)
    return SyncResult(inserted=inserted, scanned=scanned, by_browser=by_browser, errors=errors)


@app.post("/api/history/clear", response_model=ClearHistoryResponse)
def clear_history(payload: ClearHistoryRequest, _: None = Depends(require_api_access)) -> ClearHistoryResponse:
    deleted_events, deleted_reports = storage.clear_history(include_reports=payload.include_reports)

    browser_deleted: dict[str, int] = {}
    browser_errors: dict[str, str] = {}
    if payload.clear_browser_history:
        if payload.confirm_phrase != "DELETE MY BROWSER HISTORY":
            raise HTTPException(
                status_code=400,
                detail="Invalid confirmation phrase for browser history deletion.",
            )
        browser_deleted, browser_errors = clear_browser_history(payload.browsers)

    return ClearHistoryResponse(
        deleted_events=deleted_events,
        deleted_reports=deleted_reports,
        browser_deleted=browser_deleted,
        browser_errors=browser_errors,
    )


@app.post("/api/history/window/delete", response_model=DeleteWindowResponse)
def delete_history_window(
    payload: DeleteWindowRequest, _: None = Depends(require_api_access)
) -> DeleteWindowResponse:
    target_date = _parse_target_date(payload.date)
    deleted = storage.delete_events_by_capture_window(
        target_date,
        payload.capture_start_hour,
        payload.capture_end_hour,
    )
    return DeleteWindowResponse(
        date=target_date.isoformat(),
        capture_start_hour=payload.capture_start_hour,
        capture_end_hour=payload.capture_end_hour,
        deleted_events=deleted,
    )


@app.get("/api/permissions", response_model=PermissionStatusResponse)
def permissions(_: None = Depends(require_api_access)) -> PermissionStatusResponse:
    return PermissionStatusResponse(checked_at=datetime.now(), browsers=collect_permission_status())


def _parse_target_date(day: str | None) -> date:
    try:
        return date.fromisoformat(day) if day else date.today()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc


def _to_report_response(report: dict) -> ReportResponse:
    return ReportResponse(
        date=report["date"],
        model=report["model"],
        summary=report["summary"],
        highlights=report["highlights"],
        risk_flags=report["risk_flags"],
        details=report.get("details") or {},
        reasoning_trace=report.get("reasoning_trace"),
        source_events=report["source_events"],
        generated_at=datetime.fromisoformat(report["generated_at"])
        if isinstance(report["generated_at"], str)
        else report["generated_at"],
    )


def _build_or_get_report(target_date: date, force_refresh: bool) -> dict:
    events = storage.list_events_by_date(target_date, limit=settings.report_max_events)
    if not events:
        raise HTTPException(status_code=404, detail="No events available for this date. Run sync first.")

    cached = storage.get_daily_report(target_date)
    if cached and not force_refresh:
        current_count = min(storage.count_events_by_date(target_date), settings.report_max_events)
        if int(cached["source_events"]) == int(current_count):
            return cached

    try:
        report = generate_daily_report(target_date, events)
    except Exception as exc:
        logger.exception("Failed to generate AI report", exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to generate AI report.") from exc

    storage.save_daily_report(
        report_date=target_date,
        model=report["model"],
        summary=report["summary"],
        highlights=report["highlights"],
        risk_flags=report["risk_flags"],
        details=report.get("details"),
        reasoning_trace=report.get("reasoning_trace"),
        source_events=report["source_events"],
        generated_at=report["generated_at"],
    )
    report["generated_at"] = report["generated_at"].isoformat()
    return report


@app.get("/api/today", response_model=DailySnapshot)
def today_snapshot(day: str | None = None, _: None = Depends(require_api_access)) -> DailySnapshot:
    target_date = _parse_target_date(day)

    if day is None:
        total_today = storage.count_events_by_date(target_date)
        if total_today == 0:
            latest_date = storage.latest_event_date()
            if latest_date is not None:
                target_date = latest_date

    timeline = storage.list_events_by_date(target_date, limit=settings.report_max_events)
    top_domains = storage.top_domains_by_date(target_date)
    total_events = storage.count_events_by_date(target_date)
    return DailySnapshot(
        date=target_date.isoformat(),
        total_events=total_events,
        top_domains=top_domains,
        timeline=timeline,
    )


@app.get("/api/search", response_model=SearchResponse)
def search_history(
    q: str = Query(min_length=1),
    limit: int = Query(default=30, ge=1, le=100),
    _: None = Depends(require_api_access),
) -> SearchResponse:
    results, total = storage.search_events(q, limit=limit)
    domains: list[str] = []
    for event in results:
        if event.domain not in domains:
            domains.append(event.domain)
        if len(domains) == 4:
            break
    similar = storage.similar_events_by_domains(
        domains=domains,
        exclude_urls={event.url for event in results},
        limit=min(20, limit),
    )
    return SearchResponse(query=q, total_matches=total, results=results, similar=similar)


@app.post("/api/report", response_model=ReportResponse)
def build_report(payload: ReportRequest, _: None = Depends(require_api_access)) -> ReportResponse:
    target_date = _parse_target_date(payload.date)
    report = _build_or_get_report(target_date, payload.force_refresh)
    return _to_report_response(report)


@app.get("/api/report", response_model=ReportResponse)
def get_report(day: str | None = None, _: None = Depends(require_api_access)) -> ReportResponse:
    target_date = _parse_target_date(day)

    report = storage.get_daily_report(target_date)
    if not report:
        raise HTTPException(status_code=404, detail="No report generated for this date.")

    return _to_report_response(report)


@app.get("/api/report/pdf")
def download_report_pdf(
    day: str | None = None,
    force_refresh: bool = False,
    _: None = Depends(require_api_access),
) -> Response:
    target_date = _parse_target_date(day)
    report = _build_or_get_report(target_date, force_refresh)
    pdf_bytes = build_report_pdf(report)
    filename = f"wave-report-{target_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
