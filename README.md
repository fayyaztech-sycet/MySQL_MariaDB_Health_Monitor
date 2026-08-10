# MySQL Profiler — Performance Monitoring & Query Intelligence Platform

A production-grade monitoring agent for MySQL/MariaDB databases. It continuously
collects server status, slow-query stats, InnoDB internals and OS metrics, then
analyzes query performance, estimates memory pressure, emits rule-based
recommendations and alerts, and renders a live dashboard plus daily HTML reports.

Think of it as a lightweight **Percona PMM + MySQLTuner** tailored for a
MariaDB/ERP environment.

---

## Features

- **Collectors** — OS metrics (psutil), MySQL status & sizes, process list,
  slow queries (via `performance_schema` digests), InnoDB status
- **Analysis** — query ranking (most expensive / worst latency), EXPLAIN-based
  index hints, memory-pressure estimation, rule-based recommendations
- **Alerts** — high CPU, low available RAM, high disk, deadlocks, slow queries
- **Dashboard** — FastAPI + Plotly HTML pages (Overview, Queries, Server Health)
- **JSON API** — `/api/*` endpoints with API-key auth
- **Reports** — daily `mysql-report-YYYY-MM-DD.html` with a health score
- **Scheduler** — APScheduler cadences: 5s system, 1m MySQL, 1h analysis, daily report
- **Docker** — single image, optional dedicated worker

---

## Tech Stack

Python 3.12+, FastAPI, SQLAlchemy (SQLite storage), mysql-connector-python,
psutil, pandas, plotly, jinja2, APScheduler, pydantic-settings, Docker.

---

## Project Structure

```
app/
├── main.py                 # FastAPI app + lifespan (starts scheduler)
├── config.py               # env-driven settings
├── db.py                   # SQLite engine + sessions
├── models.py               # ORM models
├── mysql_connection.py     # MySQL connection helpers
├── collectors/             # system, mysql_status, processlist, slow_queries, innodb
├── analyzers/              # query, index, memory, recommendation engine, analyze job
├── alerts/                 # alerting rules
├── scheduler/              # APScheduler jobs
├── reports/                # charts + html report generator
└── api/                    # routes + dashboard templates
tests/                      # pytest suite
run_worker.py               # optional standalone scheduler worker
Dockerfile / docker-compose.yml
```

---

## Setup & Run

### 1. Prerequisites
- Python 3.12+
- A reachable MySQL/MariaDB server (local or remote)

### 2. Environment configuration
Copy the example env file and edit it:

```bash
cp .env.example .env
```

The main settings (see [.env.example](.env.example) for all options):

```ini
# Target MySQL / MariaDB database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database

# Web server (host/port for the dashboard + API)
APP_HOST=0.0.0.0
APP_PORT=8000

# Alert thresholds, collection cadences, API token...
API_TOKEN=changeme-token
```

> Credentials are read from `.env` only — never commit real credentials.
> `.env` is git-ignored; `.env.example` is the committed template.

### 3. Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the app
```bash
uvicorn app.main:app --host $APP_HOST --port $APP_PORT
```

Or with a custom port explicitly:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

The scheduler starts automatically with the app and begins collecting metrics.

### 5. Database migrations (automatic)

Schema is managed with **Alembic** (`alembic.ini` + `migrations/`). Migrations
run **automatically on every app start/restart** (inside `app/db.py`, invoked
from the FastAPI lifespan), so the SQLite schema always matches the models —
no manual step is needed.

- A **fresh** database is fully created and stamped by `alembic upgrade head`.
- A **pre-Alembic** database (created by an older build) is detected and
  stamped at the current head instead of being re-created.
- To author a new migration after changing `app/models.py`:
  ```bash
  alembic revision --autogenerate -m "describe the change"
  ```
  and review the generated file in `migrations/versions/` before it is applied
  on the next boot.

### 6. Open the dashboard
- Dashboard: http://localhost:8000/
- Queries:   http://localhost:8000/dashboard/queries
- Health:    http://localhost:8000/dashboard/health
- API docs:  http://localhost:8000/docs

---

## Run as a standalone worker (optional)

To run collectors without serving HTTP (e.g. a dedicated worker):

```bash
python run_worker.py
```

> Run **either** the API (which embeds the scheduler) **or** a worker — never
> both against the same monitored MySQL server, or metrics will be double-collected.

---

## Run with Docker

```bash
docker compose up -d
```

The API listens on `http://localhost:8000`. Configuration is passed through
environment variables (set in `.env` or the compose `environment` block).

---

## API Endpoints

All `/api/*` endpoints require the API key via the `X-API-Key` header (unless
`API_TOKEN` is left at its default `changeme-token`).

| Endpoint | Description |
|---|---|
| `/api/overview` | server + latest system metrics + counts |
| `/api/queries` | most expensive + worst latency queries |
| `/api/server-health` | recent system metric series |
| `/api/alerts` | recent alerts |
| `/api/recommendations` | recent recommendations |
| `/api/reports` | generated report registry |

---

## Tests

```bash
pip install -r requirements.txt   # includes pytest
pytest
```

The suite uses a stub MySQL connector, so no live database is required.

---

## Reports

A daily HTML report is generated at `reports/mysql-report-YYYY-MM-DD.html`
(default schedule: 02:05 UTC). It includes a 0–100 health score, a problem
summary, and charts.

---

## Configuration Reference

All settings are read from environment variables (via `.env`). See
[.env.example](.env.example) for the full list, including alert thresholds
(`ALERT_CPU_HIGH`, `ALERT_MEM_AVAIL_LOW`, `ALERT_DISK_HIGH`,
`ALERT_SLOW_QUERY_MS`, `ALERT_DEADLOCK_TRIGGER`) and collection cadences
(`SYSTEM_INTERVAL`, `MYSQL_INTERVAL`, `ANALYZE_INTERVAL`, `REPORT_HOUR`).
