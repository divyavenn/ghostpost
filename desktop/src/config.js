/**
 * Configuration management for Floodme Desktop
 */

const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const CONFIG_FILE = path.join(app.getPath('userData'), 'config.json');

/**
 * Default configuration
 */
const DEFAULT_CONFIG = {
    username: '',
    backendUrl: 'http://localhost:8000',
    pollInterval: 60000, // 60 seconds
    sessionFile: path.join(app.getPath('userData'), 'twitter_session.json'),
    headless: true,
    autoStart: true
};

/**
 * Load configuration from disk
 */
function loadConfig() {
    try {
        if (fs.existsSync(CONFIG_FILE)) {
            const data = fs.readFileSync(CONFIG_FILE, 'utf8');
            const config = JSON.parse(data);
            console.log('Configuration loaded from:', CONFIG_FILE);
            return { ...DEFAULT_CONFIG, ...config };
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }

    console.log('Using default configuration');
    return DEFAULT_CONFIG;
}

/**
 * Save configuration to disk
 */
function saveConfig(config) {
    try {
        const mergedConfig = { ...DEFAULT_CONFIG, ...config };
        fs.writeFileSync(CONFIG_FILE, JSON.stringify(mergedConfig, null, 2));
        console.log('Configuration saved to:', CONFIG_FILE);
        return true;
    } catch (error) {
        console.error('Error saving config:', error);
        return false;
    }
}

/**
 * Get session file path
 */
function getSessionFile() {
    const config = loadConfig();
    return config.sessionFile;
}

module.exports = {
    loadConfig,
    saveConfig,
    getSessionFile,
    DEFAULT_CONFIG
};
