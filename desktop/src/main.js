/**
 * Floodme Desktop App - Main Process
 *
 * This is the main Electron process that runs in the background.
 * It starts the polling loop and manages the system tray.
 */

const { app, Tray, Menu, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { startPollingLoop, stopPollingLoop } = require('./polling');
const { loadConfig, saveConfig } = require('./config');

let tray = null;
let mainWindow = null;
let isPolling = false;

/**
 * Create the system tray icon
 */
function createTray() {
    // Try to use icon, fallback to default if not found
    const iconPath = path.join(__dirname, '../assets/icon.png');

    try {
        tray = new Tray(iconPath);
    } catch (error) {
        // If icon not found, create tray without custom icon (will use default)
        console.log('Icon not found, using default system icon');
        // On macOS, we can use a template image that adapts to light/dark mode
        tray = new Tray(path.join(__dirname, '../assets/IconTemplate.png'));
    }

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Floodme Desktop',
            enabled: false
        },
        { type: 'separator' },
        {
            label: isPolling ? '✓ Polling Active' : '○ Polling Inactive',
            enabled: false
        },
        { type: 'separator' },
        {
            label: 'Configure',
            click: () => {
                showConfigWindow();
            }
        },
        {
            label: isPolling ? 'Stop Polling' : 'Start Polling',
            click: () => {
                if (isPolling) {
                    stopPollingLoop();
                    isPolling = false;
                } else {
                    startPollingLoop();
                    isPolling = true;
                }
                createTray(); // Refresh menu
            }
        },
        { type: 'separator' },
        {
            label: 'Show Logs',
            click: () => {
                showLogsWindow();
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                stopPollingLoop();
                app.quit();
            }
        }
    ]);

    tray.setToolTip('Floodme Desktop - Background automation');
    tray.setContextMenu(contextMenu);
}

/**
 * Show configuration window
 */
function showConfigWindow() {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.focus();
        return;
    }

    mainWindow = new BrowserWindow({
        width: 600,
        height: 400,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        },
        title: 'Floodme Configuration'
    });

    mainWindow.loadFile(path.join(__dirname, '../views/config.html'));

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

/**
 * Show logs window
 */
function showLogsWindow() {
    const logsWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        },
        title: 'Floodme Logs'
    });

    logsWindow.loadFile(path.join(__dirname, '../views/logs.html'));
}

/**
 * App initialization
 */
app.whenReady().then(async () => {
    console.log('Floodme Desktop starting...');

    // Load configuration
    const config = loadConfig();

    if (!config.username || !config.backendUrl) {
        // Show config window on first run
        await dialog.showMessageBox({
            type: 'info',
            title: 'Welcome to Floodme Desktop',
            message: 'Please configure your settings before starting.',
            buttons: ['OK']
        });
        showConfigWindow();
    } else {
        // Start polling automatically
        startPollingLoop();
        isPolling = true;
    }

    // Create system tray
    createTray();

    console.log('Floodme Desktop started successfully');
});

/**
 * Keep app running in background even when all windows are closed
 */
app.on('window-all-closed', (e) => {
    // Don't quit - keep running in background
    e.preventDefault();
});

/**
 * Handle app activation (macOS)
 */
app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        showConfigWindow();
    }
});

/**
 * Set app to start on login
 */
app.setLoginItemSettings({
    openAtLogin: true,
    openAsHidden: true
});

console.log('App will start automatically on login');
