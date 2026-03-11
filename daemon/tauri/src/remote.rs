use crate::config::{Config, ConfigState, PlatformAccountState};
use crate::cookies;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct PairingCompleteResponse {
    daemon_token: String,
    device: PairingDevice,
    user_info: PairingUserInfo,
    platform_preferences: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct PairingDevice {
    id: String,
}

#[derive(Debug, Deserialize)]
struct PairingUserInfo {
    user_id: String,
    email: Option<String>,
    twitter_handle: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DaemonConfigResponse {
    device: DaemonDevice,
    platform_preferences: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct DaemonDevice {
    accounts: HashMap<String, PlatformAccountState>,
}

#[derive(Debug, Serialize)]
pub struct RemoteSyncResponse {
    pub paired: bool,
    pub platform_preferences: Vec<String>,
    pub linked_accounts: HashMap<String, PlatformAccountState>,
}

fn backend_base_url(config: &Config) -> String {
    config
        .ghostpost_api_base_url
        .trim_end_matches('/')
        .to_string()
}

fn machine_id_fallback() -> String {
    let host = std::env::var("HOSTNAME")
        .ok()
        .or_else(|| std::env::var("COMPUTERNAME").ok())
        .unwrap_or_else(|| "unknown-host".to_string());
    let user = std::env::var("USER")
        .ok()
        .or_else(|| std::env::var("USERNAME").ok())
        .unwrap_or_else(|| "unknown-user".to_string());
    format!("{}:{}", host, user)
}

fn detect_accounts(platforms: &[String]) -> HashMap<String, PlatformAccountState> {
    let state = cookies::load_combined_state();
    let mut out: HashMap<String, PlatformAccountState> = HashMap::new();

    for platform in platforms {
        let key = platform.to_lowercase();
        let site_state = state.sites.get(&key);
        let account: Option<String> = None;
        let status = if let Some(site) = site_state {
            if site.cookies.is_empty() {
                "logged_out".to_string()
            } else {
                "logged_in".to_string()
            }
        } else {
            "logged_out".to_string()
        };

        out.insert(
            key,
            PlatformAccountState {
                status,
                account,
                updated_at: None,
            },
        );
    }

    out
}

pub async fn pair_device(
    state: Arc<ConfigState>,
    pair_code: String,
    device_name: Option<String>,
    machine_id: Option<String>,
) -> Result<Config, String> {
    let config = state.get();
    let base_url = backend_base_url(&config);
    let client = Client::new();
    let payload = json!({
        "pair_code": pair_code,
        "device": {
            "name": device_name.unwrap_or_else(|| "Ghostpost Desktop".to_string()),
            "os": std::env::consts::OS,
            "daemon_version": env!("CARGO_PKG_VERSION"),
            "machine_id": machine_id.unwrap_or_else(machine_id_fallback),
        }
    });

    let response = client
        .post(format!("{}/desktop/pairing/complete", base_url))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Pairing request failed: {}", e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Pairing failed: {}", body));
    }

    let pairing: PairingCompleteResponse = response
        .json()
        .await
        .map_err(|e| format!("Invalid pairing response: {}", e))?;

    state.update(|cfg| {
        cfg.daemon_token = Some(pairing.daemon_token);
        cfg.paired_device_id = Some(pairing.device.id);
        cfg.paired_user_id = Some(pairing.user_info.user_id);
        cfg.paired_user_email = pairing.user_info.email;
        cfg.paired_twitter_handle = pairing.user_info.twitter_handle;
        cfg.platform_preferences = if pairing.platform_preferences.is_empty() {
            vec!["twitter".to_string()]
        } else {
            pairing.platform_preferences
        };
    })?;

    Ok(state.get())
}

pub async fn refresh_remote_state(state: Arc<ConfigState>) -> Result<RemoteSyncResponse, String> {
    let config = state.get();
    let Some(token) = config.daemon_token.clone() else {
        return Ok(RemoteSyncResponse {
            paired: false,
            platform_preferences: config.platform_preferences,
            linked_accounts: config.linked_accounts,
        });
    };

    let base_url = backend_base_url(&config);
    let client = Client::new();

    let config_response = client
        .get(format!("{}/desktop/config", base_url))
        .header("x-daemon-token", token.clone())
        .send()
        .await
        .map_err(|e| format!("Failed to fetch daemon config: {}", e))?;

    if !config_response.status().is_success() {
        let body = config_response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Failed to fetch daemon config: {}", body));
    }

    let daemon_config: DaemonConfigResponse = config_response
        .json()
        .await
        .map_err(|e| format!("Invalid daemon config response: {}", e))?;

    let detected_accounts = detect_accounts(&daemon_config.platform_preferences);
    let sync_payload = json!({
        "accounts": detected_accounts
    });

    let sync_response = client
        .post(format!("{}/desktop/accounts/sync", base_url))
        .header("x-daemon-token", token)
        .json(&sync_payload)
        .send()
        .await
        .map_err(|e| format!("Failed to sync accounts: {}", e))?;

    if !sync_response.status().is_success() {
        let body = sync_response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Failed to sync accounts: {}", body));
    }

    let synced = daemon_config.device.accounts;
    state.update(|cfg| {
        cfg.platform_preferences = daemon_config.platform_preferences.clone();
        cfg.linked_accounts = synced.clone();
    })?;

    Ok(RemoteSyncResponse {
        paired: true,
        platform_preferences: daemon_config.platform_preferences,
        linked_accounts: synced,
    })
}
