from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic import model_validator


BrowserName = Literal["chrome", "brave", "safari"]


class SyncRequest(BaseModel):
    lookback_hours: int = Field(default=24, ge=1, le=720)
    include_all_history: bool = False
    browsers: list[BrowserName] | None = None
    capture_start_hour: int | None = Field(default=None, ge=0, le=23)
    capture_end_hour: int | None = Field(default=None, ge=0, le=23)

    @model_validator(mode="after")
    def validate_capture_window(self) -> "SyncRequest":
        start = self.capture_start_hour
        end = self.capture_end_hour
        if (start is None) ^ (end is None):
            raise ValueError("capture_start_hour and capture_end_hour must be provided together.")
        return self


class HistoryEvent(BaseModel):
    browser: str
    url: str
    title: str
    domain: str
    visited_at: datetime
    visit_count: int = 1


class SyncResult(BaseModel):
    inserted: int
    scanned: int
    by_browser: dict[str, int]
    errors: dict[str, str]


class DailySnapshot(BaseModel):
    date: str
    total_events: int
    top_domains: list[dict[str, Any]]
    timeline: list[HistoryEvent]


class ReportRequest(BaseModel):
    date: str | None = None
    force_refresh: bool = False


class ReportDetails(BaseModel):
    narrative: str = ""
    deep_research_paper: str = ""
    important_highlights: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    behavior_patterns: list[str] = Field(default_factory=list)
    time_insights: list[str] = Field(default_factory=list)
    category_insights: list[str] = Field(default_factory=list)
    intent_signals: list[str] = Field(default_factory=list)
    focus_gaps: list[str] = Field(default_factory=list)
    action_plan_7d: list[str] = Field(default_factory=list)
    methodology_notes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    date: str
    model: str
    summary: str
    highlights: list[str]
    risk_flags: list[str]
    details: ReportDetails = Field(default_factory=ReportDetails)
    reasoning_trace: str | None = None
    source_events: int
    generated_at: datetime


class BrowserPermission(BaseModel):
    browser: BrowserName
    path: str
    exists: bool
    readable: bool
    status: Literal["ready", "missing", "permission_required", "error"]
    message: str


class PermissionStatusResponse(BaseModel):
    checked_at: datetime
    browsers: list[BrowserPermission]


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    results: list[HistoryEvent]
    similar: list[HistoryEvent]


class ClearHistoryRequest(BaseModel):
    include_reports: bool = True
    clear_browser_history: bool = False
    browsers: list[BrowserName] | None = None
    confirm_phrase: str | None = None


class ClearHistoryResponse(BaseModel):
    deleted_events: int
    deleted_reports: int
    browser_deleted: dict[str, int] = Field(default_factory=dict)
    browser_errors: dict[str, str] = Field(default_factory=dict)


class DeleteWindowRequest(BaseModel):
    date: str | None = None
    capture_start_hour: int = Field(ge=0, le=23)
    capture_end_hour: int = Field(ge=0, le=23)


class DeleteWindowResponse(BaseModel):
    date: str
    capture_start_hour: int
    capture_end_hour: int
    deleted_events: int
