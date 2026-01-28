/**
 * Simple logging utility
 */

const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const LOG_FILE = path.join(app.getPath('userData'), 'floodme.log');
const MAX_LOG_SIZE = 5 * 1024 * 1024; // 5MB

/**
 * Write log entry
 */
function writeLog(level, message) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [${level}] ${message}\n`;

    // Console output
    console.log(logEntry.trim());

    // File output
    try {
        // Rotate log if too large
        if (fs.existsSync(LOG_FILE)) {
            const stats = fs.statSync(LOG_FILE);
            if (stats.size > MAX_LOG_SIZE) {
                const backupFile = LOG_FILE + '.old';
                fs.renameSync(LOG_FILE, backupFile);
            }
        }

        fs.appendFileSync(LOG_FILE, logEntry);
    } catch (error) {
        console.error('Failed to write to log file:', error);
    }
}

/**
 * Log info message
 */
function logInfo(message) {
    writeLog('INFO', message);
}

/**
 * Log error message
 */
function logError(message) {
    writeLog('ERROR', message);
}

/**
 * Log success message
 */
function logSuccess(message) {
    writeLog('SUCCESS', message);
}

/**
 * Log warning message
 */
function logWarning(message) {
    writeLog('WARNING', message);
}

/**
 * Get log file path
 */
function getLogFilePath() {
    return LOG_FILE;
}

/**
 * Read recent logs
 */
function getRecentLogs(lines = 100) {
    try {
        if (!fs.existsSync(LOG_FILE)) {
            return '';
        }

        const content = fs.readFileSync(LOG_FILE, 'utf8');
        const allLines = content.split('\n');
        const recentLines = allLines.slice(-lines);
        return recentLines.join('\n');
    } catch (error) {
        return `Error reading logs: ${error.message}`;
    }
}

module.exports = {
    logInfo,
    logError,
    logSuccess,
    logWarning,
    getLogFilePath,
    getRecentLogs
};
