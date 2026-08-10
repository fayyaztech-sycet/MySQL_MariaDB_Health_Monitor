// PM2 ecosystem file — MySQL Profiler (FastAPI + embedded APScheduler)
//
// The app embeds its scheduler, so it MUST run as a single process
// (--workers 1). Do not scale this with the cluster mode / more workers,
// or metrics will be collected multiple times.
//
// Usage:
//   pm2 start ecosystem.config.js                 # start the API (default)
//   pm2 start ecosystem.config.js --only worker   # standalone scheduler worker (optional)
//   pm2 save && pm2 startup                       # persist across reboots
//   pm2 logs mysql-profiler-api                   # follow logs
//   pm2 monit                                     # resource monitor
//
// Host/port are read from .env (APP_HOST / APP_PORT); defaults to 0.0.0.0:8000.

'use strict';

const fs = require('fs');
const path = require('path');

// Minimal .env parser — pulls APP_HOST/APP_PORT out of the project .env so
// PM2 stays in sync with the same file pydantic-settings reads.
function loadEnv(file) {
  const env = {};
  let content;
  try {
    content = fs.readFileSync(file, 'utf8');
  } catch {
    return env; // .env missing — fall back to defaults below
  }
  for (const raw of content.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const env = loadEnv(path.join(__dirname, '.env'));
const HOST = env.APP_HOST || '0.0.0.0';
const PORT = env.APP_PORT || '8000';

const api = {
  name: 'mysql-profiler-api',
  cwd: __dirname,

  // Use the venv python directly; run uvicorn as a module so reload/workers
  // semantics are identical to a normal `uvicorn app.main:app` invocation.
  script: '.venv/bin/python',
  args: `-m uvicorn app.main:app --host ${HOST} --port ${PORT} --workers 1`,

  interpreter: 'none', // script is the python binary itself

  env: {
    NODE_ENV: 'production',
  },

  autorestart: true,
  restart_delay: 5000,
  max_memory_restart: '512M',

  out_file: 'logs/pm2-api.out.log',
  error_file: 'logs/pm2-api.err.log',
  merge_logs: true,
  time: true,
};

// Optional standalone worker — run collectors/reports WITHOUT serving HTTP.
// IMPORTANT (see README): run either the API (which embeds the scheduler) OR
// the worker — never both against the same SQLite file / MySQL server, or
// metrics will be double-collected. Uncomment and use `--only worker` to run.
//
// const worker = {
//   name: 'mysql-profiler-worker',
//   cwd: __dirname,
//   script: '.venv/bin/python',
//   args: 'run_worker.py',
//   interpreter: 'none',
//   autorestart: true,
//   restart_delay: 5000,
//   max_memory_restart: '512M',
//   out_file: 'logs/pm2-worker.out.log',
//   error_file: 'logs/pm2-worker.err.log',
//   merge_logs: true,
//   time: true,
// };

module.exports = {
  apps: [api],
};
