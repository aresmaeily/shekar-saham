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
    title: "شکار سهام v0.9 Ultimate - بهتر از فراز و نوآوران"
  });

  // For personal use - load local server
  // Change to https://your-server.com for production
  const startUrl = process.env.SHEKAR_URL || 'http://127.0.0.1:8000';
  
  mainWindow.loadURL(startUrl);

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
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
        { label: 'چارت فارکس', click: () => mainWindow.loadURL(startUrl + '/#forex') },
        { label: 'اندیکاتور شخصی', click: () => mainWindow.webContents.executeJavaScript('document.querySelector(\'[data-tab="excellent"]\')?.click()') }
      ]
    },
    {
      label: 'راهنما',
      submenu: [
        { label: 'درباره شکار سهام', click: () => shell.openExternal('https://github.com/shekar-saham') }
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
