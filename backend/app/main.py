from __future__ import annotations

import hashlib
import json
import ipaddress
import logging
from datetime import date, datetime, timezone
from hmac import compare_digest
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
from backend.app.services.rate_limit import SlidingWindowRateLimiter
from backend.app.services.report_pdf import build_report_pdf


logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wave", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=settings.allow_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Wave-Token", settings.request_id_header],
)
app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)
if settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

storage = WaveStorage(settings.wave_db_path)
rate_limiter = SlidingWindowRateLimiter(max_requests=settings.api_rate_limit_per_minute, window_seconds=60)
started_at = datetime.now(timezone.utc)

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend"
STATIC_ROOT = FRONTEND_ROOT / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")

BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
HTML_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-src 'self' blob:; "
    "base-uri 'none'; "
    "form-action 'self'"
)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "Wave startup | env=%s | db=%s | rate_limit=%s/%s",
        settings.environment,
        settings.wave_db_path,
        settings.api_rate_limit_per_minute,
        "min",
    )
    # Force a lightweight DB call early so deployment failures surface on boot.
    storage.count_events_by_date(date.today())


def _asset_version() -> str:
    candidates = [
        FRONTEND_ROOT / "index.html",
        STATIC_ROOT / "styles.css",
        STATIC_ROOT / "app.js",
    ]
    newest = max(int(path.stat().st_mtime) for path in candidates if path.exists())
    return str(newest)


def _render_index_html() -> str:
    template = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
    return (
        template.replace("__WAVE_API_TOKEN_JSON__", json.dumps(settings.api_token))
        .replace("__WAVE_ASSET_VERSION__", _asset_version())
    )


def _is_loopback_host(host: str) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def require_api_access(request: Request) -> None:
    client_host = _request_ip(request)
    if settings.restrict_to_loopback and not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Forbidden")

    provided_token = request.headers.get("X-Wave-Token", "")
    if not provided_token or not compare_digest(provided_token, settings.api_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    request_id = request.headers.get(settings.request_id_header, "").strip() or uuid4().hex
    request.state.request_id = request_id

    is_api = request.url.path.startswith("/api/")
    if settings.rate_limit_enabled and is_api and request.url.path != "/api/health":
        ip = _request_ip(request)
        rate_key = f"{ip}:{request.method}:{request.url.path}"
        rate = rate_limiter.consume(rate_key)
        if not rate.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again shortly.",
                    "request_id": request_id,
                },
                headers={
                    settings.request_id_header: request_id,
                    "Retry-After": str(rate.retry_after_seconds),
                    "X-RateLimit-Limit": str(settings.api_rate_limit_per_minute),
                    "X-RateLimit-Remaining": str(rate.remaining),
                },
            )
        request.state.rate_limit_remaining = rate.remaining

    response = await call_next(request)

    response.headers[settings.request_id_header] = request_id
    for header, value in BASE_SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)

    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"

    if request.url.path == "/":
        response.headers["Content-Security-Policy"] = HTML_CSP

    if settings.rate_limit_enabled and is_api and request.url.path != "/api/health":
        response.headers["X-RateLimit-Limit"] = str(settings.api_rate_limit_per_minute)
        remaining = getattr(request.state, "rate_limit_remaining", None)
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    headers = dict(getattr(exc, "headers", {}) or {})
    headers[settings.request_id_header] = request_id
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "errors": exc.errors(),
            "request_id": request_id,
        },
        headers={settings.request_id_header: request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.exception("Unhandled exception [request_id=%s] on %s", request_id, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "request_id": request_id,
        },
        headers={settings.request_id_header: request_id},
    )


@app.get("/")
def index() -> HTMLResponse:
    html = _render_index_html()
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health() -> dict[str, object]:
    uptime_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
    return {
        "status": "ok",
        "environment": settings.environment,
        "uptime_seconds": uptime_seconds,
    }


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


def _events_fingerprint(events) -> str:
    digest = hashlib.sha256()
    for event in events:
        digest.update(
            (
                f"{event.browser}|{event.visited_at.isoformat()}|{event.url}|{event.title}|{event.visit_count}\n"
            ).encode("utf-8", "ignore")
        )
    return digest.hexdigest()


def _build_or_get_report(target_date: date, force_refresh: bool) -> dict:
    events = storage.list_events_by_date(target_date, limit=settings.report_max_events)
    if not events:
        raise HTTPException(status_code=404, detail="No events available for this date. Run sync first.")

    current_count = min(storage.count_events_by_date(target_date), settings.report_max_events)
    current_fingerprint = _events_fingerprint(events)
    cached = storage.get_daily_report(target_date)
    if cached and not force_refresh:
        details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
        cached_fingerprint = str(details.get("_report_fingerprint") or "")
        if int(cached["source_events"]) == int(current_count) and cached_fingerprint == current_fingerprint:
            return cached

    try:
        report = generate_daily_report(target_date, events)
    except Exception as exc:
        logger.exception("Failed to generate AI report", exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to generate AI report.") from exc

    details = report.get("details") if isinstance(report.get("details"), dict) else {}
    details["_report_fingerprint"] = current_fingerprint
    report["details"] = details

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
    limit: int = Query(default=30, ge=1),
    _: None = Depends(require_api_access),
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be blank.")

    safe_limit = max(1, min(limit, settings.search_max_limit))
    results, total = storage.search_events(query, limit=safe_limit)
    domains: list[str] = []
    for event in results:
        if event.domain not in domains:
            domains.append(event.domain)
        if len(domains) == 4:
            break
    similar = storage.similar_events_by_domains(
        domains=domains,
        exclude_urls={event.url for event in results},
        limit=min(20, safe_limit),
    )
    return SearchResponse(query=query, total_matches=total, results=results, similar=similar)


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
