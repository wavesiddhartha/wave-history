from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import Iterable

from dotenv import load_dotenv


load_dotenv()


def _parse_int(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError:
            value = default

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _parse_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw.strip())
        except ValueError:
            value = default

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_csv(name: str, default: Iterable[str]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return tuple(default)
    parts = [part.strip() for part in raw.split(",")]
    clean = tuple(part for part in parts if part)
    return clean or tuple(default)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    wave_db_path: Path
    environment: str
    log_level: str
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_temperature: float
    ai_top_p: float
    ai_max_tokens: int
    ai_connect_timeout_sec: float
    ai_read_timeout_sec: float
    report_max_events: int
    search_max_limit: int
    api_token: str
    allow_origin_regex: str
    allowed_hosts: tuple[str, ...]
    restrict_to_loopback: bool
    rate_limit_enabled: bool
    api_rate_limit_per_minute: int
    sqlite_busy_timeout_ms: int
    gzip_minimum_size: int
    request_id_header: str


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_environment = os.getenv("WAVE_ENV", "development").strip().lower() or "development"
_log_level = (os.getenv("WAVE_LOG_LEVEL", "INFO").strip().upper() or "INFO")
_valid_log_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
if _log_level not in _valid_log_levels:
    _log_level = "INFO"

_api_token_env = os.getenv("WAVE_API_TOKEN", "").strip()
if _environment in {"production", "prod"} and not _api_token_env:
    raise RuntimeError("WAVE_API_TOKEN is required when WAVE_ENV=production.")

settings = Settings(
    project_root=ROOT,
    data_dir=DATA_DIR,
    wave_db_path=DATA_DIR / "wave.db",
    environment=_environment,
    log_level=_log_level,
    ai_base_url=os.getenv("WAVE_AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    ai_api_key=os.getenv("WAVE_AI_API_KEY", ""),
    ai_model=os.getenv("WAVE_AI_MODEL", "moonshotai/kimi-k2-thinking"),
    ai_temperature=_parse_float("WAVE_AI_TEMPERATURE", 1.0, minimum=0.0, maximum=2.0),
    ai_top_p=_parse_float("WAVE_AI_TOP_P", 0.9, minimum=0.0, maximum=1.0),
    ai_max_tokens=_parse_int("WAVE_AI_MAX_TOKENS", 16384, minimum=512, maximum=65536),
    ai_connect_timeout_sec=_parse_float("WAVE_AI_CONNECT_TIMEOUT_SEC", 5.0, minimum=1.0, maximum=30.0),
    ai_read_timeout_sec=_parse_float("WAVE_AI_READ_TIMEOUT_SEC", 16.0, minimum=4.0, maximum=120.0),
    report_max_events=_parse_int("WAVE_REPORT_MAX_EVENTS", 500, minimum=50, maximum=5000),
    search_max_limit=_parse_int("WAVE_SEARCH_MAX_LIMIT", 100, minimum=10, maximum=500),
    api_token=_api_token_env or token_urlsafe(32),
    allow_origin_regex=os.getenv(
        "WAVE_ALLOW_ORIGIN_REGEX",
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    ),
    allowed_hosts=_parse_csv("WAVE_ALLOWED_HOSTS", ("127.0.0.1", "localhost")),
    restrict_to_loopback=_parse_bool("WAVE_RESTRICT_TO_LOOPBACK", True),
    rate_limit_enabled=_parse_bool("WAVE_RATE_LIMIT_ENABLED", True),
    api_rate_limit_per_minute=_parse_int("WAVE_API_RATE_LIMIT_PER_MINUTE", 240, minimum=30, maximum=5000),
    sqlite_busy_timeout_ms=_parse_int("WAVE_SQLITE_BUSY_TIMEOUT_MS", 5000, minimum=500, maximum=60000),
    gzip_minimum_size=_parse_int("WAVE_GZIP_MINIMUM_SIZE", 1024, minimum=256, maximum=65536),
    request_id_header=os.getenv("WAVE_REQUEST_ID_HEADER", "X-Request-ID").strip() or "X-Request-ID",
)
