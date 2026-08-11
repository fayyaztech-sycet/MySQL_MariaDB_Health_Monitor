# CLAUDE.md

This file provides guidance for working with the **MySQL Profiler** codebase.

## What this project is

A production-grade monitoring agent for MySQL/MariaDB. It continuously collects
server status, slow-query stats, InnoDB internals and OS metrics, then analyzes
query performance, estimates memory pressure, emits rule-based recommendations
and alerts, and renders a live dashboard plus daily HTML reports. Think of it as
a lightweight **Percona PMM + MySQLTuner** tailored for a MariaDB/ERP environment.

Stack: Python 3.12+, FastAPI, SQLAlchemy (SQLite storage), mysql-connector-python,
psutil, pandas, plotly, jinja2, APScheduler, pydantic-settings, bcrypt, Docker.

## Project layout

```
app/
├── main.py                 # FastAPI app factory + lifespan (starts scheduler)
├── config.py               # env-driven Settings (pydantic-settings)
├── db.py                   # SQLite engine + session factory + Alembic migration runner
├── models.py               # SQLAlchemy ORM models
├── mysql_connection.py     # MySQL connection helpers
├── collectors/             # system, mysql_status, processlist, slow_queries, innodb
├── analyzers/              # query, index, memory, recommendation engine, analyze job
├── alerts/alerting.py      # alerting rules
├── scheduler/jobs.py       # APScheduler job registration + runner
├── reports/                # charts + html report generator
└── api/                    # routes (JSON API + dashboard pages) + templates
tests/                      # pytest suite (stubbed MySQL connector, no live DB)
run_worker.py               # standalone scheduler worker (no HTTP)
migrations/                 # Alembic version scripts
alembic.ini
pyproject.toml              # deps + pytest config (testpaths = tests)
ecosystem.config.js         # PM2 process config
Dockerfile / docker-compose.yml
```

## Key architecture concepts

### Collectors self-register by import
Collectors are plain modules that define `collect(session, conn) -> int rows_written`
and register themselves. `app/collectors/__init__.py` calls
`register("name", module.collect)` from `app/scheduler/jobs.py` (registration is
idempotent). `app/main.py` `register_collectors()` imports the `collectors`,
`analyzers`, `alerts`, and `reports` packages so their side-effect imports wire
everything into the scheduler. To add a collector: create a module, import it in
`app/collectors/__init__.py`, and register it.

### Scheduler runs in-process
`app/scheduler/jobs.py` builds an APScheduler `BackgroundScheduler`. Each job
(`_collect`) opens **its own** DB session and a fresh MySQL connection, so a
failure in one collector is isolated. Cadences: 5s system, 60s mysql, 3600s
analyze, daily report (cron hour `report_hour`, minute 5). Only jobs for
registered collectors are added — if none are registered the scheduler isn't
started.

### DB is SQLite, schema managed by Alembic, migrated on every boot
`app/db.py` `init_db()` runs `_run_migrations()` on **every app start/restart**.
It detects a pre-Alembic DB (tables present but no `alembic_version` row) and
stamps it at head instead of recreating; otherwise runs `alembic upgrade head`.
After changing `app/models.py`, author a migration with
`alembic revision --autogenerate -m "describe"` and review the generated file.
Use `session_scope()` (commit/rollback) for jobs; `get_db()` (no commit) for
FastAPI request dependencies.

### Auth has two layers
- **Dashboard pages**: protected by a session cookie (`SessionMiddleware`, 2-hour
  TTL) when `DASHBOARD_PASSWORD_HASH` is set (bcrypt). Empty hash = no password.
- **JSON API** (`/api/*`): requires the `X-API-Key` header matching `API_TOKEN`.
- The dashboard is a single live page (`/`) updated over a WebSocket; `/logs`
  lists alerts with date filter + Live toggle. Templates in `app/api/templates/`.

## Configuration

All settings come from environment variables via `.env` (see `.env.example`).
Key settings in `app/config.py`:

- Target DB: `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`
- Web: `APP_HOST` (default 0.0.0.0), `APP_PORT` (default 8000)
- Storage: `SQLITE_PATH` (default `monitor.db`)
- Cadences: `SYSTEM_INTERVAL` (5s), `MYSQL_INTERVAL` (60s), `ANALYZE_INTERVAL` (3600s),
  `REPORT_HOUR` (2)
- Alerts: `ALERT_CPU_HIGH`, `ALERT_MEM_AVAIL_LOW`, `ALERT_DISK_HIGH`,
  `ALERT_SLOW_QUERY_MS`, `ALERT_DEADLOCK_TRIGGER`
- API auth: `API_TOKEN` (default `changeme-token`)
- Dashboard auth: `DASHBOARD_PASSWORD_HASH` (bcrypt; empty = open),
  `SESSION_SECRET`

**Never commit real credentials.** Copy `.env.example` → `.env` and edit locally.
`.env`, `*.db`, and `reports/*.html` are git-ignored.

## Common commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # includes pytest; add -e .[dev] for httpx

# Run the API (embeds the scheduler)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run a standalone worker (collectors only, no HTTP)
python run_worker.py

# Tests (uses a stub MySQL connector — no live DB required)
pytest

# New Alembic migration after editing app/models.py
alembic revision --autogenerate -m "describe the change"
```

## Critical constraints & gotchas

- **Run either the API (which embeds the scheduler) OR a standalone worker — never
  both against the same monitored MySQL server**, or metrics get double-collected.
- The daily report is written to `reports/mysql-report-YYYY-MM-DD.html` with a
  0–100 health score.
- `monitor.db` is the local history database; it is re-created/upgraded on every
  start via Alembic, so a broken migration surfaces at boot.
- Tests must stay DB-free: use the `FakeConn`/`FakeCursor` stubs in
  `tests/conftest.py`, never hit a real MySQL server.

## Test conventions

`tests/conftest.py` provides a temp SQLite DB (`db_path`/`session` fixtures) and
fake MySQL connection stubs. `FakeConn(routes)` accepts a dict of
SQL-keyword → rows or a callable router. Keep new tests on this pattern.
