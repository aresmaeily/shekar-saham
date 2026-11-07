// Supervised local backend lifecycle (WAVE-N remainder, OA-1/OA-4; 2026-11-06).
//
// ADDITIVE module — resolves the recorded WAVE-N residual ("the shell does
// not spawn the backend — documented limitation"): the shell now STARTS and
// SUPERVISES the bundled backend as a LOCAL, loopback-only child process:
//
// - BOUNDED STARTUP: a bounded startup window with a /api/health poll on
//   127.0.0.1 only; timeout ⇒ an HONEST degraded state (surfaced in the
//   window via a local data: URL status page — never a silent fallthrough).
// - GRACEFUL SHUTDOWN: app quit ⇒ SIGTERM-equivalent (process.kill), a
//   bounded grace window, then a forced kill; never left running silently.
// - CRASH RECOVERY: unexpected backend exit ⇒ bounded restarts with
//   backoff; exhausting the budget ⇒ honest degraded state in the UI.
// - SAFE LOCAL BINDING: the backend is spawned with HOST=127.0.0.1 (the
//   loopback interface only) — the supervised process is never reachable
//   from the network; health checks talk to 127.0.0.1 only.
//
// HONEST DISCLOSURE (kept from the runbook, now narrower): the packaged
// payload contains the backend SOURCE (backend/app + requirements.txt);
// a Python 3.11+ interpreter must exist on the target machine. If none is
// found, the module refuses SILENTLY-DEGRADED states — the window shows
// the honest reason and the runbook diagnostics cover it. This module
// performs no fetch of any kind: no remote egress, no updater, no fetch —
// the only endpoint it touches is the loopback /api/health probe.
//
// Statically pinned by backend/tests/test_wda_electron_shell_gates.py
// (WAVE-N remainder section).

const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const os = require('os');
const fs = require('fs');

const BACKEND_STARTUP_TIMEOUT_MS = 90000; // bounded startup window
const HEALTH_POLL_INTERVAL_MS = 500;
const MAX_RESTARTS = 3;                   // bounded crash-recovery budget
const RESTART_BACKOFF_MS = 3000;
const GRACEFUL_SHUTDOWN_MS = 10000;       // bounded graceful stop, then force

// The supervised backend binds LOOPBACK ONLY — structural, not advisory.
const LOCAL_HOST = '127.0.0.1';
const DEFAULT_PORT = process.env.RADAR_BACKEND_PORT || '8000';

let child = null;           // the supervised backend process
let state = 'stopped';      // stopped | starting | running | degraded | stopping
let restarts = 0;           // bounded crash-recovery counter
let intentionalStop = false;
let healthTimer = null;
let statusListener = null;  // main.js callback for honest UI status updates

function _now() {
  return Date.now();
}

function _setState(next, detail) {
  state = next;
  if (statusListener) {
    try { statusListener(next, detail || ''); } catch (e) { /* never fatal */ }
  }
}

function onStatus(listener) {
  statusListener = listener;
}

function getState() {
  return { state, restarts, pid: child ? child.pid : null, host: LOCAL_HOST, port: DEFAULT_PORT };
}

// Resolve a Python interpreter HONESTLY — WAVE-T3 (MR-I-02, 2026-11-07):
// 1) PREFERRED: the installer bundles a PINNED embedded CPython runtime at
//    <resources>/python-runtime/python.exe (python.org 3.12.10 embeddable
//    amd64, MD5-verified against python.org's published value at build time;
//    PSF LICENSE VERSION 2 notice bundled at
//    python-runtime/LICENSE_PYTHON.txt). Its dependency bundle lives at
//    <resources>/site-packages and is wired through the runtime's own
//    python312._pth (append-only, done at build time and proven by a CI
//    import smoke). First launch therefore needs NO system Python, NO pip,
//    NO venv, and NO network.
// 2) FALLBACK (development only): the Windows py launcher / RADAR_PYTHON /
//    python3 on PATH — the pre-WAVE-T3 spawn behavior preserved (same cmd
//    and args; the returned object merely gains the bundled:false metadata
//    flag) so a dev checkout still boots without a bundled runtime present.
// Nothing is fetched at runtime; an unverified runtime is never fetched or claimed.
function resolvePythonCommand() {
  const isWin = process.platform === 'win32';
  const resPath = process.resourcesPath;
  if (resPath) {
    const bundledExe = path.join(resPath, 'python-runtime', 'python.exe');
    if (fs.existsSync(bundledExe)) {
      return { cmd: bundledExe, args: [], bundled: true };
    }
  }
  return isWin
    ? { cmd: 'py', args: ['-3'], bundled: false }
    : { cmd: process.env.RADAR_PYTHON || 'python3', args: [], bundled: false };
}

// Locate the bundled backend directory (OA-1 WAVE-N remainder).
// - Packaged builds: electron-builder extraResources places the payload
//   OUTSIDE app.asar at <install>/resources/backend — a REAL filesystem
//   path a Python child can execute from (Electron exposes it via
//   process.resourcesPath).
// - Development runs: the sibling ../backend of this file.
function resolveBackendDir() {
  const resPath = process.resourcesPath;
  if (resPath && fs.existsSync(path.join(resPath, 'backend', 'app', 'main.py'))) {
    return path.join(resPath, 'backend');
  }
  const dev = path.join(__dirname, '..', 'backend');
  if (fs.existsSync(path.join(dev, 'app', 'main.py'))) return dev;
  return null;
}

// OA-1 data-directory contract: on-disk stores live OUTSIDE the install
// directory (survives upgrade/uninstall). Packaged builds relocate the
// backend's DATA_DIR to %APPDATA%/radar-bourse via RADAR_DATA_DIR (honored
// by backend/app/core/config.py); development runs keep the repo default.
function resolveDataDir() {
  if (process.env.RADAR_DATA_DIR && process.env.RADAR_DATA_DIR.trim()) {
    return process.env.RADAR_DATA_DIR.trim();
  }
  const packaged = process.resourcesPath && fs.existsSync(path.join(process.resourcesPath, 'backend', 'app', 'main.py'));
  if (!packaged) return null; // development: repo DATA_DIR default
  const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
  return path.join(appData, 'radar-bourse');
}

// Loopback-only health probe: GET 127.0.0.1:<port> path /api/health.
function probeHealth(port) {
  return new Promise((resolve) => {
    const req = http.request(
      { host: LOCAL_HOST, port: Number(port), path: '/api/health', method: 'GET', timeout: 2000 },
      (res) => {
        res.resume();
        resolve(res.statusCode && res.statusCode < 500);
      }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}

function startBackendOnce(onReady, onDegrade) {
  const backendDir = resolveBackendDir();
  if (!backendDir) {
    _setState('degraded', 'bundled-backend-directory-missing');
    if (onDegrade) onDegrade('bundled-backend-directory-missing');
    return;
  }
  const py = resolvePythonCommand();
  _setState('starting', 'spawning:' + py.cmd);
  const startedAt = _now();
  const dataDir = resolveDataDir();
  try {
    child = spawn(py.cmd, py.args.concat([
      '-m', 'uvicorn', 'app.main:app',
      '--host', LOCAL_HOST,       // SAFE LOCAL BINDING (structural)
      '--port', DEFAULT_PORT,
    ]), {
      cwd: backendDir,
      env: Object.assign({}, process.env, {
        HOST: LOCAL_HOST,         // belt-and-braces: app config too
        PORT: DEFAULT_PORT,
        PYTHONUNBUFFERED: '1',
        // OA-1: stores live outside the install directory
        RADAR_DATA_DIR: dataDir || process.env.RADAR_DATA_DIR || '',
        // keep the app's own fail-closed defaults untouched:
        AI2_ENABLED: process.env.AI2_ENABLED || '0',
        SCHEDULER_ENABLED: process.env.SCHEDULER_ENABLED || '0',
      }),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });
  } catch (e) {
    _setState('degraded', 'spawn-failed:' + e.message);
    if (onDegrade) onDegrade('spawn-failed');
    return;
  }
  child.on('error', (err) => {
    // spawn/ENOENT (no Python on PATH) — honest degraded state, never silent
    console.error('[radar-backend] spawn error:', err.message);
    child = null;
    _setState('degraded', 'python-not-found');
    if (onDegrade) onDegrade('python-not-found');
  });
  child.on('exit', (code, signal) => {
    const wasIntentional = intentionalStop;
    child = null;
    clearTimeout(healthTimer);
    if (wasIntentional) {
      _setState('stopped', 'intentional-stop');
      return;
    }
    // CRASH RECOVERY (bounded): unexpected exit while supervised
    if (restarts < MAX_RESTARTS && !wasIntentional) {
      restarts += 1;
      console.error('[radar-backend] backend exited (code=' + code + ', signal=' + signal + '); bounded restart ' + restarts + '/' + MAX_RESTARTS);
      _setState('starting', 'bounded-restart:' + restarts);
      setTimeout(() => startBackendOnce(onReady, onDegrade), RESTART_BACKOFF_MS * restarts);
    } else {
      _setState('degraded', 'restart-budget-exhausted');
      if (onDegrade) onDegrade('restart-budget-exhausted');
    }
  });

  // BOUNDED STARTUP + health polling (loopback only)
  healthTimer = setInterval(async () => {
    const healthy = await probeHealth(DEFAULT_PORT);
    if (healthy) {
      clearInterval(healthTimer);
      healthTimer = null;
      restarts = 0; // a healthy run resets the bounded recovery budget
      _setState('running', 'health-ok');
      if (onReady) onReady();
      return;
    }
    if (_now() - startedAt > BACKEND_STARTUP_TIMEOUT_MS) {
      clearInterval(healthTimer);
      healthTimer = null;
      // bounded startup window exhausted — honest degraded state
      _setState('degraded', 'startup-timeout');
      if (onDegrade) onDegrade('startup-timeout');
    }
  }, HEALTH_POLL_INTERVAL_MS);
}

// Public API used by main.js (additive wiring).
function start(onReady, onDegrade) {
  if (state === 'starting' || state === 'running') {
    return; // idempotent
  }
  intentionalStop = false;
  startBackendOnce(onReady, onDegrade);
}

function stop() {
  return new Promise((resolve) => {
    intentionalStop = true;
    if (healthTimer) { clearInterval(healthTimer); healthTimer = null; }
    if (!child) {
      state = 'stopped';
      resolve();
      return;
    }
    const pid = child.pid;
    _setState('stopping', 'graceful');
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    // graceful: SIGTERM-equivalent first
    try { child.kill(); } catch (e) { /* already gone */ }
    const forceTimer = setTimeout(() => {
      // bounded grace window exhausted → forced kill
      try {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true });
        } else {
          try { process.kill(pid, 'SIGKILL'); } catch (e) { /* gone */ }
        }
      } catch (e) { /* gone */ }
      finish();
    }, GRACEFUL_SHUTDOWN_MS);
    child.on('exit', () => { clearTimeout(forceTimer); state = 'stopped'; finish(); });
  });
}

module.exports = {
  start,
  stop,
  getState,
  onStatus,
  // exported for static contract tests / diagnostics
  constants: {
    BACKEND_STARTUP_TIMEOUT_MS,
    HEALTH_POLL_INTERVAL_MS,
    MAX_RESTARTS,
    RESTART_BACKOFF_MS,
    GRACEFUL_SHUTDOWN_MS,
    LOCAL_HOST,
  },
};
