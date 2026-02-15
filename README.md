# Wave

Wave is a privacy-consented browser memory app. It ingests local browsing history from Safari, Chrome, and Brave, stores it locally, and generates an AI "Today on the Internet" report.

## What this MVP does

- Reads browser history from local macOS history databases (Safari/Chrome/Brave)
- Normalizes and stores events in a local SQLite database (`data/wave.db`)
- Shows a clean dashboard with:
  - total events, top domains, and timeline
  - history search (title/domain/url) with similar links
  - capture window control (for example 06:00 to 12:00 local time)
  - AI-generated deep daily report with important highlights, key facts, long summary, behavior patterns, time/category insights, recommendations, and optional reasoning trace
  - one-click PDF download of the generated daily report
  - Safari permission status check (ready/missing/permission required)
- one-click full Safari history import
- one-click delete Wave app history and reports
- optional live sync every 15 seconds
- Uses Kimi K2 via OpenAI-compatible API (NVIDIA integration endpoint)

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
cp .env.example .env
```

Then set `WAVE_AI_API_KEY` in `.env`.
You can tune Kimi behavior with `WAVE_AI_TEMPERATURE`, `WAVE_AI_TOP_P`, and `WAVE_AI_MAX_TOKENS`.

3. Run the app:

```bash
uvicorn backend.app.main:app --reload --port 8080
```

For platforms that auto-detect FastAPI from repo root, you can also run:

```bash
uvicorn main:app --reload --port 8080
```

4. Open the UI:

- [http://127.0.0.1:8080](http://127.0.0.1:8080)

## Production run

For non-dev deployment, avoid `--reload` and set a fixed API token:

```bash
export WAVE_ENV=production
export WAVE_API_TOKEN="replace_with_long_random_secret"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --workers 2
```

## Security defaults

- API endpoints require a per-run token (`X-Wave-Token`) injected into the served UI.
- API access is restricted to local loopback clients.
- CORS is restricted to `localhost`/`127.0.0.1` origins.
- Stored URLs are sanitized to remove sensitive query parameters/fragments before persistence.
- AI report prompts include redacted event lines (no raw full URLs).
- Rate limiting is enabled on `/api/*` (except `/api/health`) by default.
- Every response includes a request id header (`X-Request-ID`) for traceability.
- Security headers and CSP are enabled on app responses.

## macOS permissions required

To read Safari and Chromium history databases reliably, grant Full Disk Access to your terminal/Python runtime:

- System Settings -> Privacy & Security -> Full Disk Access
- Add your terminal app (Terminal/iTerm) and restart it

Without permission, the app still runs, but sync may show browser-specific errors.

## API endpoints

All `/api/*` endpoints except `/api/health` require header `X-Wave-Token` (the UI injects this automatically).

- `GET /api/health` - service health, environment and uptime
- `POST /api/sync` - ingest browser history  
  request options:
  - `lookback_hours` (default `24`)
  - `include_all_history` (`true` for full import, especially Safari)
  - `browsers` (`[\"safari\"]`, `[\"chrome\",\"brave\",\"safari\"]`, etc.)
  - `capture_start_hour` and `capture_end_hour` (`0-23`, both required together; same value means full day)
- `GET /api/permissions` - check browser history access and permission status
- `GET /api/search` - search saved history with `q` and optional `limit`
- `GET /api/today` - fetch timeline and top domains for a day
- `POST /api/report` - generate AI report for a day (`force_refresh` optional)
- `GET /api/report` - fetch cached report
- `GET /api/report/pdf` - download the day report as PDF (`day` and `force_refresh` optional)
- `POST /api/history/clear` - delete all saved Wave history (and optionally reports)
- `POST /api/history/window/delete` - delete only events in selected capture window for a day
  - body: `date` (optional, defaults today), `capture_start_hour`, `capture_end_hour`
  - optional native browser wipe:
    - set `clear_browser_history=true`
    - include `confirm_phrase=\"DELETE MY BROWSER HISTORY\"`
    - optionally pass `browsers`

## System design used

- Ingestion layer: browser-specific collectors normalize raw SQLite history rows into one `HistoryEvent` schema.
- Storage layer: `history_events` table with uniqueness key `(browser, url, visited_at)` for idempotent syncs.
- Query layer: date-bounded timeline query + grouped domain aggregation for fast dashboard rendering.
- Analysis layer: Kimi K2 report generation with constrained JSON schema for deterministic UI payloads.

## Data structures and algorithms used

- Normalized event object (`HistoryEvent`) for consistent cross-browser processing.
- Deduplication by SQLite unique index plus `INSERT OR IGNORE` (efficient set-like behavior).
- Domain aggregation through SQL `GROUP BY domain ORDER BY count DESC`.
- Time-window filtering per browser using native timestamp epochs:
  - Chromium: microseconds since 1601-01-01
  - Safari: seconds since 2001-01-01

## Notes

- All raw history data is stored locally in SQLite.
- API keys are read from environment variables. Do not hardcode secrets in code.
- If an API key is exposed, rotate it immediately in the provider dashboard.

## Deployment

Local Docker (recommended for reproducible runs):

```bash
docker build -t wave:local .
docker run --rm -p 8000:8000 -e WAVE_ENV=production -e WAVE_API_TOKEN=changeme -v "$PWD/data":/app/data wave:local
```

Docker Compose (quick start):

```bash
docker-compose up --build
```

GitHub: The repository includes a GitHub Actions workflow that builds and publishes a Docker image to GitHub Container Registry. To enable automatic Render deployments, set the `RENDER_API_KEY` and `RENDER_SERVICE_ID` repository secrets.

Render: A `render.yaml` manifest is included. Connect your GitHub repo in Render, add `WAVE_ENV` and `WAVE_API_TOKEN` as service environment variables in the Render dashboard, and Render will pick up the Dockerfile on push.

