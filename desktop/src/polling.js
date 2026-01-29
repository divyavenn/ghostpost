/**
 * Polling loop for checking backend for pending jobs
 */

const axios = require('axios');
const { loadConfig } = require('./config');
const { executeJob } = require('./job-executor');
const { logInfo, logError, logSuccess } = require('./logger');

let pollingInterval = null;
let isPolling = false;

/**
 * Poll backend for pending jobs
 */
async function pollForJobs() {
    const config = loadConfig();

    if (!config.username || !config.backendUrl) {
        logError('Configuration incomplete. Please set username and backend URL.');
        return;
    }

    try {
        logInfo('Polling for jobs...');

        // 1. Check for pending jobs
        const response = await axios.get(
            `${config.backendUrl}/desktop-jobs/${config.username}/pending`,
            { timeout: 10000 }
        );

        const jobs = response.data;

        if (!jobs || jobs.length === 0) {
            logInfo('No pending jobs');
            return;
        }

        logInfo(`Found ${jobs.length} pending job(s)`);

        // 2. Execute each job
        for (const job of jobs) {
            try {
                logInfo(`Executing job ${job.id}: ${job.job_type}`);

                const result = await executeJob(job);

                // 3. Report success
                await axios.post(
                    `${config.backendUrl}/desktop-jobs/${job.id}/complete`,
                    result,
                    { timeout: 30000 }
                );

                logSuccess(`Job ${job.id} completed successfully`);
            } catch (error) {
                logError(`Job ${job.id} failed: ${error.message}`);

                // 4. Report failure to backend
                try {
                    await axios.post(
                        `${config.backendUrl}/desktop-jobs/${job.id}/fail`,
                        { error: error.message },
                        { timeout: 10000 }
                    );
                } catch (reportError) {
                    logError(`Failed to report job failure: ${reportError.message}`);
                }
            }
        }
    } catch (error) {
        if (error.code === 'ECONNREFUSED') {
            logError('Cannot connect to backend server. Is it running?');
        } else if (error.code === 'ETIMEDOUT') {
            logError('Backend request timed out');
        } else {
            logError(`Polling error: ${error.message}`);
        }
    }
}

/**
 * Start the polling loop
 */
function startPollingLoop() {
    if (isPolling) {
        logInfo('Polling already active');
        return;
    }

    const config = loadConfig();

    logInfo(`Starting polling loop (interval: ${config.pollInterval / 1000}s)`);

    // Poll immediately on start
    pollForJobs();

    // Then poll at regular intervals
    pollingInterval = setInterval(pollForJobs, config.pollInterval);

    isPolling = true;
}

/**
 * Stop the polling loop
 */
function stopPollingLoop() {
    if (!isPolling) {
        return;
    }

    logInfo('Stopping polling loop');

    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }

    isPolling = false;
}

/**
 * Check if polling is active
 */
function isPollingActive() {
    return isPolling;
}

module.exports = {
    startPollingLoop,
    stopPollingLoop,
    isPollingActive,
    pollForJobs
};
