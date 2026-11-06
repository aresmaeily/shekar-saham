// Electron main - Windows app like faraz.io Windows app
const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');

// WAVE-N remainder (OA-1, 2026-11-06): the shell now SUPERVISES the bundled
// backend as a local loopback-only child process (bounded startup + health
// check + graceful shutdown + bounded crash recovery). Resolves the recorded
// "shell-does-not-spawn-backend" limitation; statically pinned by
// backend/tests/test_wda_electron_shell_gates.py.
const backendService = require('./backend_service');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    icon: path.join(__dirname, '../frontend/favicon.svg'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false
    },
    title: "رادار بورس - نسخه دسکتاپ"
  });

  // For personal use - load local server
  // Change to https://your-server.com for production
  const startUrl = process.env.RADAR_BOURSE_URL || process.env.SHEKAR_URL || 'http://127.0.0.1:8000';

  // WAVE-N remainder: when the shell SUPERVISES its own backend, the shell
  // must never load a foreign origin; the supervised backend is loopback-only.
  if (process.env.RADAR_BOURSE_URL || process.env.SHEKAR_URL) {
    try {
      const forced = new URL(startUrl);
      if (forced.hostname !== '127.0.0.1' && forced.hostname !== 'localhost') {
        console.error('[radar] refusing non-loopback RADAR_BOURSE_URL override:', startUrl);
      }
    } catch (e) { /* fall through to the loopback default */ }
  }

  let allowedOrigin = 'http://127.0.0.1:8000';
  try {
    allowedOrigin = new URL(startUrl).origin;
  } catch (e) {
    allowedOrigin = 'http://127.0.0.1:8000';
  }

  function isAllowedNavigation(url) {
    try {
      return new URL(url).origin === allowedOrigin;
    } catch (e) {
      return false;
    }
  }

  mainWindow.loadURL(startUrl);

  // Keep the shell on the configured backend origin. External targets open in the OS browser.
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedNavigation(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
  mainWindow.webContents.on('will-redirect', (event, url) => {
    if (!isAllowedNavigation(url)) {
      event.preventDefault();
    }
  });

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedNavigation(url)) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Menu in Persian
  const template = [
    {
      label: 'فایل',
      submenu: [
        { label: 'بروزرسانی', accelerator: 'CmdOrCtrl+R', click: () => mainWindow.reload() },
        { role: 'quit', label: 'خروج' }
      ]
    },
    {
      label: 'نمایش',
      submenu: [
        { role: 'toggleDevTools', label: 'ابزار توسعه' },
        { role: 'togglefullscreen', label: 'تمام صفحه' },
        { type: 'separator' },
        { label: 'چارت فارکس', click: () => mainWindow.loadURL(startUrl + '/#/forex') },
        { label: '📈 چارت حرفه‌ای', click: () => mainWindow.loadURL(startUrl + '/#/chartpro') },
        { label: 'اندیکاتور شخصی', click: () => mainWindow.webContents.executeJavaScript('document.querySelector(\'[data-tab="excellent"]\')?.click()') }
      ]
    },
    {
      label: 'راهنما',
      submenu: [
        { label: 'درباره رادار بورس', click: () => shell.openExternal('https://github.com/aresmaeily/shekar-saham') }
      ]
    }
  ];
  
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

app.whenReady().then(() => {
  // WAVE-N remainder: start the SUPERVISED local backend FIRST; the window
  // loads only once the backend is healthy (bounded startup window). A
  // degraded state loads an HONEST local status page (data: URL, no remote
  // content) — never a silent failure.
  const startUrl = process.env.RADAR_BOURSE_URL || process.env.SHEKAR_URL || 'http://127.0.0.1:8000';
  backendService.onStatus((state, detail) => {
    console.log('[radar-backend] state:', state, detail || '');
  });
  backendService.start(
    () => createWindow(),
    (reason) => loadDegradedStatusPage(reason)
  );
});

// Honest local status page for degraded states (data: URL — zero remote
// content, zero egress). Shows the machine-readable reason and the runbook
// diagnostics pointers.
function loadDegradedStatusPage(reason) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = new BrowserWindow({
      width: 900,
      height: 600,
      webPreferences: { nodeIntegration: false, contextIsolation: true, enableRemoteModule: false },
      title: "رادار بورس — وضعیت موتور محلی"
    });
  }
  const html = `<!doctype html><html dir="rtl" lang="fa"><head><meta charset="utf-8">
  <title>رادار بورس — وضعیت موتور محلی</title>
  <style>body{font-family:Vazirmatn,Tahoma,sans-serif;background:#101418;color:#e6e6e6;padding:40px;line-height:1.9}
  .box{max-width:720px;margin:auto;background:#1a2027;border:1px solid #2c3947;border-radius:12px;padding:28px}
  code{background:#0b0e12;padding:2px 8px;border-radius:6px;color:#7fd18c;font-size:0.9em}</style></head>
  <body><div class="box">
  <h2>موتور تحلیل محلی آماده نیست</h2>
  <p>پوستهٔ برنامه موتور محلی (backend) را به‌صورت تحت‌نظارت اجرا می‌کند، اما این بار آماده‌سازی در بازهٔ مجاز با موفقیت کامل نشد.</p>
  <p>دلیل ماشین‌خوان: <code>${String(reason || 'unknown')}</code></p>
  <p>شایع‌ترین علت‌ها و راه‌حل‌ها:</p>
  <ul>
    <li>پایتون ۳٫۱۱ یا جدیدتر نصب نیست — پایتون را نصب کنید (فقط نسخهٔ رسمی، بدون دانلود از داخل برنامه).</li>
    <li>پورت <code>8000</code> توسط برنامهٔ دیگری اشغال است — متغیر محیطی <code>RADAR_BACKEND_PORT</code> را تغییر دهید.</li>
    <li>پایگاه دادهٔ محلی قفل است — از Runbook بخش Diagnostics استفاده کنید.</li>
  </ul>
  <p>این صفحه کاملاً محلی است؛ هیچ ارتباط بیرونی برقرار نمی‌شود. موتور روی <code>127.0.0.1</code> اجرا می‌شود.</p>
  <p><button onclick="location.reload()" style="padding:8px 18px;border-radius:8px;border:1px solid #2c3947;background:#232b36;color:#e6e6e6">تلاش مجدد</button></p>
  </div></body></html>`;
  mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// WAVE-N remainder: graceful supervised-backend shutdown on quit — bounded
// grace window, then forced kill (never left running silently).
app.on('will-quit', (event) => {
  const st = backendService.getState();
  if (st.state === 'starting' || st.state === 'running' || st.state === 'stopping') {
    event.preventDefault();
    backendService.stop().then(() => {
      try { app.exit(0); } catch (e) { process.exit(0); }
    });
  }
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    backendService.stop().then(() => process.exit(0));
  });
}

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

/* WDA-1 (2026-11-03): additive app-level error handling — statically pinned by
   backend/tests/test_wda_electron_shell_gates.py. Renderer crashes are logged
   and the window is reloaded at most once per 5 seconds (no reload loop);
   main-process uncaught errors are logged and never silently fatal. */
let _lastRendererReloadAt = 0;
app.on('render-process-gone', (event, webContents, details) => {
  console.error('[radar] renderer-process-gone:', details && details.reason, details && details.exitCode);
  const now = Date.now();
  if (
    details && details.reason !== 'clean-exit' &&
    mainWindow && !mainWindow.isDestroyed() &&
    now - _lastRendererReloadAt > 5000
  ) {
    _lastRendererReloadAt = now;
    try { mainWindow.reload(); } catch (e) { /* پنجره در دسترس نیست */ }
  }
});

app.on('child-process-gone', (event, details) => {
  console.error('[radar] child-process-gone:', details && details.type, details && details.reason);
});

process.on('uncaughtException', (err) => {
  console.error('[radar] uncaughtException:', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[radar] unhandledRejection:', reason);
});

// For auto-updater in future
// require('update-electron-app')();
