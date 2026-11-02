// Electron main - Windows app like faraz.io Windows app
const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');

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

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// For auto-updater in future
// require('update-electron-app')();
