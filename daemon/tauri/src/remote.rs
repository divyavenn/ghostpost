use crate::config::{Config, ConfigState, PlatformAccountState};
use crate::cookies;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tracing::{error, info, warn};

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

#[derive(Debug, Deserialize, Serialize)]
pub struct StandaloneDraftResponse {
    pub message: String,
    pub status: String,
    pub draft_id: Option<String>,
    pub queued: Option<bool>,
    pub username: String,
}

#[derive(Debug, Serialize)]
struct CreateStandaloneDraftRequest {
    url: String,
    title: String,
    author: Option<String>,
    content_type: String,
    text_sample: Option<String>,
    notes: Option<String>,
    scraped_content: Option<String>,
    image_url: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RemoteDesktopJob {
    id: String,
    job_type: String,
    params: Value,
}

#[derive(Debug, Deserialize)]
struct LocalEnqueueResponse {
    success: bool,
    task_ids: Vec<String>,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct LocalTaskEnvelope {
    success: bool,
    task: Option<LocalTask>,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct LocalTask {
    status: String,
    error: Option<String>,
    retry_count: i32,
}

fn backend_base_url(config: &Config) -> String {
    config
        .ghostpost_api_base_url
        .trim_end_matches('/')
        .to_string()
}

fn local_daemon_base_url(config: &Config) -> String {
    format!("http://127.0.0.1:{}", config.port)
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

pub async fn create_standalone_draft(
    state: Arc<ConfigState>,
    url: String,
    title: String,
    author: Option<String>,
    content_type: String,
    text_sample: Option<String>,
    notes: Option<String>,
    scraped_content: Option<String>,
    image_url: Option<String>,
) -> Result<StandaloneDraftResponse, String> {
    let config = state.get();
    let Some(token) = config.daemon_token.clone() else {
        return Err("Daemon is not paired with Ghostpost yet".to_string());
    };

    let payload = CreateStandaloneDraftRequest {
        url,
        title,
        author,
        content_type,
        text_sample,
        notes,
        scraped_content,
        image_url,
    };

    let client = Client::new();
    let response = client
        .post(format!("{}/desktop/standalone-drafts", backend_base_url(&config)))
        .header("x-daemon-token", token)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Failed to create Ghostpost draft: {}", e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Ghostpost draft creation failed: {}", body));
    }

    response
        .json::<StandaloneDraftResponse>()
        .await
        .map_err(|e| format!("Invalid Ghostpost draft response: {}", e))
}

async fn claim_remote_jobs(state: Arc<ConfigState>) -> Result<Vec<RemoteDesktopJob>, String> {
    let config = state.get();
    let Some(token) = config.daemon_token.clone() else {
        return Ok(vec![]);
    };

    let client = Client::new();
    let response = client
        .get(format!("{}/desktop-jobs/tasks/pending", backend_base_url(&config)))
        .header("x-desktop-token", token)
        .query(&[("supported_job_types", "POST_ALL")])
        .send()
        .await
        .map_err(|e| format!("Failed to claim remote jobs: {}", e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Failed to claim remote jobs: {}", body));
    }

    response
        .json::<Vec<RemoteDesktopJob>>()
        .await
        .map_err(|e| format!("Invalid remote jobs response: {}", e))
}

async fn complete_remote_job(
    client: &Client,
    config: &Config,
    token: &str,
    job_id: &str,
    result: Value,
) -> Result<(), String> {
    let response = client
        .post(format!(
            "{}/desktop-jobs/tasks/{}/complete",
            backend_base_url(config),
            job_id
        ))
        .header("x-desktop-token", token)
        .json(&json!({ "result": result }))
        .send()
        .await
        .map_err(|e| format!("Failed to report remote job completion: {}", e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Failed to report remote job completion: {}", body));
    }

    Ok(())
}

async fn fail_remote_job(
    client: &Client,
    config: &Config,
    token: &str,
    job_id: &str,
    error_message: &str,
) -> Result<(), String> {
    let response = client
        .post(format!(
            "{}/desktop-jobs/tasks/{}/fail",
            backend_base_url(config),
            job_id
        ))
        .header("x-desktop-token", token)
        .json(&json!({ "error": error_message }))
        .send()
        .await
        .map_err(|e| format!("Failed to report remote job failure: {}", e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Failed to report remote job failure: {}", body));
    }

    Ok(())
}

async fn enqueue_local_command(
    client: &Client,
    config: &Config,
    task: &str,
    content: &str,
    image_url: Option<&str>,
    link_url: Option<&str>,
) -> Result<Vec<String>, String> {
    let response = client
        .post(format!("{}/enqueue", local_daemon_base_url(config)))
        .json(&json!({
            "task": task,
            "content": content,
            "image_url": image_url,
            "url": link_url,
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to enqueue local {} task: {}", task, e))?;

    if !response.status().is_success() {
        let body = response
            .text()
            .await
            .unwrap_or_else(|_| "unknown error".to_string());
        return Err(format!("Local {} enqueue failed: {}", task, body));
    }

    let payload = response
        .json::<LocalEnqueueResponse>()
        .await
        .map_err(|e| format!("Invalid local {} enqueue response: {}", task, e))?;

    if !payload.success {
        return Err(
            payload
                .error
                .unwrap_or_else(|| format!("Local {} enqueue failed", task)),
        );
    }

    if payload.task_ids.is_empty() {
        return Err(format!("Local {} enqueue returned no task ids", task));
    }

    Ok(payload.task_ids)
}

async fn wait_for_local_tasks(
    client: &Client,
    config: &Config,
    task_ids: &[String],
) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(300);

    loop {
        let mut all_completed = true;

        for task_id in task_ids {
            let response = client
                .get(format!("{}/tasks/{}", local_daemon_base_url(config), task_id))
                .send()
                .await
                .map_err(|e| format!("Failed to poll local task {}: {}", task_id, e))?;

            if response.status() == reqwest::StatusCode::NOT_FOUND {
                continue;
            }

            if !response.status().is_success() {
                let body = response
                    .text()
                    .await
                    .unwrap_or_else(|_| "unknown error".to_string());
                return Err(format!("Local task {} polling failed: {}", task_id, body));
            }

            let payload = response
                .json::<LocalTaskEnvelope>()
                .await
                .map_err(|e| format!("Invalid local task {} response: {}", task_id, e))?;

            if !payload.success {
                return Err(
                    payload
                        .error
                        .unwrap_or_else(|| format!("Local task {} failed to load", task_id)),
                );
            }

            let Some(task) = payload.task else {
                all_completed = false;
                continue;
            };

            match task.status.as_str() {
                "completed" => {}
                "failed" | "auth_required" => {
                    return Err(task.error.unwrap_or_else(|| {
                        format!("Local task {} ended with status {}", task_id, task.status)
                    }));
                }
                "pending" if task.retry_count > 0 || task.error.is_some() => {
                    return Err(task.error.unwrap_or_else(|| {
                        format!("Local task {} returned to pending after a failure", task_id)
                    }));
                }
                _ => {
                    all_completed = false;
                }
            }
        }

        if all_completed {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err("Timed out waiting for local daemon tasks to complete".to_string());
        }

        tokio::time::sleep(Duration::from_secs(2)).await;
    }
}

async fn execute_remote_post_all_job(
    client: &Client,
    config: &Config,
    job: &RemoteDesktopJob,
) -> Result<Value, String> {
    let content = job
        .params
        .get("content")
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "Remote POST_ALL job is missing content".to_string())?;

    let image_url = job.params.get("image_url").and_then(|value| value.as_str());
    let link_url = job
        .params
        .get("link_url")
        .and_then(|value| value.as_str())
        .or_else(|| job.params.get("url").and_then(|value| value.as_str()))
        .map(str::trim)
        .filter(|value| !value.is_empty());

    let mut requested_platforms: Vec<&str> = Vec::new();
    if config.post_to_twitter {
        requested_platforms.push("post_x");
    }
    if config.post_to_substack {
        requested_platforms.push("post_substack");
    }
    if config.post_to_linkedin {
        requested_platforms.push("post_linkedin");
    }

    if requested_platforms.is_empty() {
        return Err("No daemon posting platforms are enabled in Settings".to_string());
    }

    let mut task_ids: Vec<String> = Vec::new();
    for task in &requested_platforms {
        let mut ids =
            enqueue_local_command(client, config, task, content, image_url, link_url).await?;
        task_ids.append(&mut ids);
    }

    wait_for_local_tasks(client, config, &task_ids).await?;

    Ok(json!({
        "local_task_ids": task_ids,
        "platforms": requested_platforms,
        "draft_id": job.params.get("draft_id").cloned().unwrap_or(Value::Null),
        "link_url": link_url,
    }))
}

pub async fn remote_job_loop(state: Arc<ConfigState>) {
    tokio::time::sleep(Duration::from_secs(3)).await;

    loop {
        let config = state.get();
        if config.daemon_token.is_none() {
            tokio::time::sleep(Duration::from_secs(15)).await;
            continue;
        }
        drop(config);

        if let Err(sync_error) = refresh_remote_state(state.clone()).await {
            warn!("[remote] account sync skipped: {}", sync_error);
        }

        let jobs = match claim_remote_jobs(state.clone()).await {
            Ok(jobs) => jobs,
            Err(claim_error) => {
                warn!("[remote] failed to claim jobs: {}", claim_error);
                tokio::time::sleep(Duration::from_secs(15)).await;
                continue;
            }
        };

        if !jobs.is_empty() {
            info!("[remote] claimed {} remote desktop job(s)", jobs.len());
        }

        for job in jobs {
            let config = state.get();
            let Some(token) = config.daemon_token.clone() else {
                break;
            };
            let client = Client::new();

            let outcome = match job.job_type.as_str() {
                "POST_ALL" => execute_remote_post_all_job(&client, &config, &job).await,
                other => Err(format!("Unsupported remote desktop job type: {}", other)),
            };

            match outcome {
                Ok(result) => {
                    if let Err(report_error) =
                        complete_remote_job(&client, &config, &token, &job.id, result).await
                    {
                        error!("[remote] {}", report_error);
                    }
                }
                Err(job_error) => {
                    warn!("[remote] job {} failed: {}", job.id, job_error);
                    if let Err(report_error) =
                        fail_remote_job(&client, &config, &token, &job.id, &job_error).await
                    {
                        error!("[remote] {}", report_error);
                    }
                }
            }
        }

        tokio::time::sleep(Duration::from_secs(15)).await;
    }
}
