// Settings window JavaScript

const { invoke } = window.__TAURI__.core;

// DOM elements — toggles
const postSubstackInput = document.getElementById('post-substack');
const postTwitterInput = document.getElementById('post-twitter');
const postGithubInput = document.getElementById('post-github');
const postLinkedinInput = document.getElementById('post-linkedin');

// DOM elements — GitHub settings
const githubSettingsBtn = document.getElementById('github-settings-btn');
const githubSettingsPanel = document.getElementById('github-settings');
const githubTokenInput = document.getElementById('github-token');
const githubRepoInput = document.getElementById('github-repo');
const diaryPathInput = document.getElementById('diary-path');
const saveGithubBtn = document.getElementById('save-github');

// DOM elements — advanced
const portInput = document.getElementById('port');
const cookiesPathEl = document.getElementById('cookies-path');
const saveAdvancedBtn = document.getElementById('save-advanced');
const ghostpostApiBaseUrlInput = document.getElementById('ghostpost-api-base-url');
const pairCodeInput = document.getElementById('pair-code');
const pairDeviceBtn = document.getElementById('pair-device-btn');
const refreshRemoteBtn = document.getElementById('refresh-remote-btn');
const pairedUserEl = document.getElementById('paired-user');
const linkedAccountsEl = document.getElementById('linked-accounts');

// DOM elements — navigation
const pageMain = document.getElementById('page-main');
const pageAdvanced = document.getElementById('page-advanced');
const advancedBtn = document.getElementById('advanced-btn');
const backBtn = document.getElementById('back-btn');

const statusEl = document.getElementById('status');

function showPage(name) {
    pageMain.classList.toggle('hidden', name !== 'main');
    pageAdvanced.classList.toggle('hidden', name !== 'advanced');
}

advancedBtn.addEventListener('click', () => showPage('advanced'));
backBtn.addEventListener('click', () => showPage('main'));

githubSettingsBtn.addEventListener('click', () => {
    githubSettingsPanel.classList.toggle('hidden');
});

function gatherConfig() {
    return {
        port: parseInt(portInput.value, 10),
        autoStart: true,
        githubToken: githubTokenInput.value || null,
        githubRepo: githubRepoInput.value || null,
        diaryPath: diaryPathInput.value,
        postToSubstack: postSubstackInput.checked,
        postToTwitter: postTwitterInput.checked,
        postToLinkedin: postLinkedinInput.checked,
        postToGithub: postGithubInput.checked,
        ghostpostApiBaseUrl: ghostpostApiBaseUrlInput.value || 'http://localhost:8000',
    };
}

async function saveConfig() {
    try {
        await invoke('save_config', gatherConfig());
        showStatus('Settings saved', 'success');
    } catch (error) {
        showStatus('Failed to save: ' + error, 'error');
    }
}

function renderPairedState(config) {
    if (config.paired_user_id) {
        pairedUserEl.textContent = `Paired: ${config.paired_twitter_handle || config.paired_user_email || config.paired_user_id}`;
    } else {
        pairedUserEl.textContent = 'Not paired';
    }

    const entries = Object.entries(config.linked_accounts || {});
    if (entries.length === 0) {
        linkedAccountsEl.textContent = 'No linked account data yet.';
        return;
    }

    linkedAccountsEl.innerHTML = entries
        .map(([platform, state]) => {
            const account = state.account || state.status || 'unknown';
            return `<div>${platform}: ${account}</div>`;
        })
        .join('');
}

async function pairDevice() {
    try {
        const pairCode = (pairCodeInput.value || '').trim();
        if (!pairCode) {
            showStatus('Enter pairing code first', 'error');
            return;
        }

        await saveConfig();
        const updated = await invoke('pair_device', {
            pairCode,
            deviceName: 'Ghostpost Desktop',
            machineId: null,
        });
        renderPairedState(updated);
        pairCodeInput.value = '';
        showStatus('Device paired successfully', 'success');
    } catch (error) {
        showStatus('Pairing failed: ' + error, 'error');
    }
}

async function refreshRemoteState() {
    try {
        await saveConfig();
        await invoke('refresh_remote_state');
        const config = await invoke('get_config');
        renderPairedState(config);
        showStatus('Remote accounts synced', 'success');
    } catch (error) {
        showStatus('Remote sync failed: ' + error, 'error');
    }
}

for (const toggle of [postSubstackInput, postTwitterInput, postGithubInput, postLinkedinInput]) {
    toggle.addEventListener('change', saveConfig);
}

saveGithubBtn.addEventListener('click', saveConfig);
saveAdvancedBtn.addEventListener('click', saveConfig);
pairDeviceBtn.addEventListener('click', pairDevice);
refreshRemoteBtn.addEventListener('click', refreshRemoteState);

async function loadConfig() {
    try {
        const config = await invoke('get_config');

        portInput.value = config.port;
        githubTokenInput.value = config.github_token || '';
        githubRepoInput.value = config.github_repo || '';
        diaryPathInput.value = config.diary_path;
        postSubstackInput.checked = config.post_to_substack;
        postTwitterInput.checked = config.post_to_twitter;
        postLinkedinInput.checked = config.post_to_linkedin;
        postGithubInput.checked = config.post_to_github;
        ghostpostApiBaseUrlInput.value = config.ghostpost_api_base_url || 'http://localhost:8000';

        renderPairedState(config);

        if (config.daemon_token) {
            try {
                await invoke('refresh_remote_state');
                const refreshed = await invoke('get_config');
                renderPairedState(refreshed);
            } catch {
                // Keep UI usable even if remote is temporarily unavailable.
            }
        }

        const cookiesPath = await invoke('get_cookies_path');
        cookiesPathEl.textContent = cookiesPath;
    } catch (error) {
        showStatus('Failed to load config: ' + error, 'error');
    }
}

function showStatus(message, type) {
    statusEl.textContent = message;
    statusEl.className = 'status ' + type;

    if (type === 'success') {
        setTimeout(() => {
            statusEl.className = 'status hidden';
        }, 2000);
    }
}

document.addEventListener('DOMContentLoaded', loadConfig);
