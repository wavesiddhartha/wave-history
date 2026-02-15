from __future__ import annotations

import os
from secrets import token_urlsafe
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    wave_db_path: Path
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_temperature: float
    ai_top_p: float
    ai_max_tokens: int
    report_max_events: int
    api_token: str


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings(
    project_root=ROOT,
    data_dir=DATA_DIR,
    wave_db_path=DATA_DIR / "wave.db",
    ai_base_url=os.getenv("WAVE_AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    ai_api_key=os.getenv("WAVE_AI_API_KEY", ""),
    ai_model=os.getenv("WAVE_AI_MODEL", "moonshotai/kimi-k2-thinking"),
    ai_temperature=float(os.getenv("WAVE_AI_TEMPERATURE", "1")),
    ai_top_p=float(os.getenv("WAVE_AI_TOP_P", "0.9")),
    ai_max_tokens=int(os.getenv("WAVE_AI_MAX_TOKENS", "16384")),
    report_max_events=int(os.getenv("WAVE_REPORT_MAX_EVENTS", "500")),
    api_token=os.getenv("WAVE_API_TOKEN", token_urlsafe(32)),
)
