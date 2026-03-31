//! Embedded Axum server for receiving cookies from Chrome extension.

use crate::config::ConfigState;
use crate::cookies::{import_browser_state, BrowserStateRequest};
use crate::reddit_research::{research_reddit_via_cdp, summarize_findings, RedditResearchRequest};
use crate::tasks::{
    supported_task_commands, CreateTaskRequest, Task, TaskCommandDescriptor, TaskQueue, TaskStatus,
    TaskType, AVAILABLE_COMMANDS,
};
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, patch, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::oneshot;
use tower_http::cors::{Any, CorsLayer};
use tracing::{error, info, warn};

/// Server state shared across handlers
pub struct ServerState {
    #[allow(dead_code)]
    pub config: Arc<ConfigState>,
    pub task_queue: TaskQueue,
}

// ImportCookiesRequest is now BrowserStateRequest from cookies module

/// Response for cookie import
#[derive(Debug, Serialize)]
pub struct ImportCookiesResponse {
    pub success: bool,
    pub message: String,
    pub cookies_imported: usize,
}

/// Error response
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub success: bool,
    pub error: String,
}

/// Health check response
#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
}

/// Request body for bookmark endpoint
#[derive(Debug, Deserialize)]
pub struct BookmarkRequest {
    /// URL to bookmark
    pub url: String,
    /// Optional excerpt (highlighted text from page)
    #[serde(default)]
    pub excerpt: Option<String>,
    /// Optional notes from the user
    #[serde(default)]
    pub notes: Option<String>,
}

/// Response for bookmark endpoint - flat structure for extension
#[derive(Debug, Serialize)]
pub struct BookmarkResponse {
    pub success: bool,
    pub task_id: Option<String>,
    pub url: Option<String>,
    pub title: Option<String>,
    pub author: Option<String>,
    pub content_type: Option<String>,
    pub excerpt: Option<String>,
    pub image_url: Option<String>,
    pub content: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct GhostpostDraftRequest {
    pub url: String,
    #[serde(default)]
    pub excerpt: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct GhostpostDraftResponse {
    pub success: bool,
    pub draft_id: Option<String>,
    pub status: Option<String>,
    pub username: Option<String>,
    pub error: Option<String>,
}

/// Request for confirming Substack post
#[derive(Debug, Deserialize)]
pub struct ConfirmSubstackPostRequest {
    pub task_id: String,
    pub status: String, // "completed" or "failed"
    #[serde(default)]
    pub error: Option<String>,
}

/// Response for task list
#[derive(Debug, Serialize)]
pub struct TaskListResponse {
    pub success: bool,
    pub tasks: Vec<Task>,
}

/// Response for supported queue commands/task-types
#[derive(Debug, Serialize)]
pub struct SupportedTasksResponse {
    pub success: bool,
    pub commands: Vec<TaskCommandDescriptor>,
}

/// Response for single task
#[derive(Debug, Serialize)]
pub struct TaskResponse {
    pub success: bool,
    pub task: Option<Task>,
    pub message: Option<String>,
}

/// Request to update task status
#[derive(Debug, Deserialize)]
pub struct UpdateTaskRequest {
    pub status: Option<TaskStatus>,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
}

/// Request body for enqueue endpoint
/// task must be one of AVAILABLE_COMMANDS (see GET /supported-tasks)
#[derive(Debug, Deserialize)]
pub struct EnqueueRequest {
    pub task: String,
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub image_url: Option<String>,
    #[serde(default)]
    pub query: Option<String>,
}

fn resolve_command_to_task_types(task: &str) -> Option<Vec<TaskType>> {
    let task_types: Vec<TaskType> = match task {
        "post_all" => vec![
            TaskType::PostSubstackNote,
            TaskType::PostTweet,
            TaskType::PostLinkedIn,
        ],
        "post_x" | "post_twitter" => vec![TaskType::PostTweet],
        "post_substack" => vec![TaskType::PostSubstackNote],
        "post_linkedin" => vec![TaskType::PostLinkedIn],
        "reply_x" => vec![TaskType::ReplyX],
        "search_x" => vec![TaskType::SearchX],
        "get_thread_x" => vec![TaskType::GetThreadX],
        "fetch_home_timeline_x" => vec![TaskType::FetchHomeTimelineX],
        "fetch_user_timeline_x" => vec![TaskType::FetchUserTimelineX],
        "deep_scrape_thread_x" => vec![TaskType::DeepScrapeThreadX],
        "shallow_scrape_thread_x" => vec![TaskType::ShallowScrapeThreadX],
        "scrape_tweets_x" => vec![TaskType::ScrapeTweetsX],
        "research_reddit" => vec![TaskType::ResearchReddit],
        _ => return None,
    };
    Some(task_types)
}

/// Request body for scrape endpoint
#[derive(Debug, Deserialize)]
pub struct ScrapeRequest {
    pub url: String,
    /// Clip start timestamp (MM:SS, HH:MM:SS, or seconds). Only used for video/audio content.
    #[serde(rename = "startTime", default)]
    pub start_time: Option<String>,
    /// Clip end timestamp (MM:SS, HH:MM:SS, or seconds). Only used for video/audio content.
    #[serde(rename = "endTime", default)]
    pub end_time: Option<String>,
    /// Download the video file (base64 in response). Only applies to YouTube.
    #[serde(rename = "downloadVideo", default)]
    pub download_video: bool,
    /// Download the audio file (base64 in response). Only applies to YouTube.
    #[serde(rename = "downloadAudio", default)]
    pub download_audio: bool,
    /// Download the transcript/markdown. Defaults to true.
    #[serde(rename = "downloadTranscript", default = "default_true")]
    pub download_transcript: bool,
    /// OpenAI API key for Whisper transcription fallback.
    #[serde(rename = "openaiApiKey", default)]
    pub openai_api_key: Option<String>,
}

fn default_true() -> bool {
    true
}

/// Response for scrape endpoint
#[derive(Debug, Serialize)]
pub struct ScrapeResponse {
    pub success: bool,
    pub markdown: Option<String>,
    pub filename: Option<String>,
    pub content_type: Option<String>,
    pub title: Option<String>,
    pub author: Option<String>,
    pub director: Option<String>,
    pub year: Option<u16>,
    pub starring: Option<Vec<String>>,
    pub error: Option<String>,
    #[serde(rename = "audioData", skip_serializing_if = "Option::is_none")]
    pub audio_data: Option<String>,
    #[serde(rename = "audioFilename", skip_serializing_if = "Option::is_none")]
    pub audio_filename: Option<String>,
    #[serde(rename = "audioMimeType", skip_serializing_if = "Option::is_none")]
    pub audio_mime_type: Option<String>,
    #[serde(rename = "videoData", skip_serializing_if = "Option::is_none")]
    pub video_data: Option<String>,
    #[serde(rename = "videoFilename", skip_serializing_if = "Option::is_none")]
    pub video_filename: Option<String>,
    #[serde(rename = "videoMimeType", skip_serializing_if = "Option::is_none")]
    pub video_mime_type: Option<String>,
}

/// Health check endpoint
async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "running".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

/// Import browser state (cookies + context) from Chrome extension
async fn import_cookies_handler(
    State(_state): State<Arc<ServerState>>,
    Json(req): Json<BrowserStateRequest>,
) -> impl IntoResponse {
    match import_browser_state(req) {
        Ok(count) => (
            StatusCode::OK,
            Json(ImportCookiesResponse {
                success: true,
                message: format!("Successfully imported {} cookies", count),
                cookies_imported: count,
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Bookmark endpoint - queues tasks immediately, processes in background
async fn bookmark_handler(
    State(state): State<Arc<ServerState>>,
    Json(req): Json<BookmarkRequest>,
) -> impl IntoResponse {
    let url = req.url.clone();
    let excerpt = req.excerpt.clone();
    let notes = req.notes.clone();
    let config = state.config.get();

    // Create tasks immediately so the extension can move on

    let payload = serde_json::json!({
        "url": &url,
        "excerpt": &excerpt,
        "notes": &notes,
    });

    // Task: LogToGitHub (always created)
    let github_task = state.task_queue.create_task(CreateTaskRequest {
        task_type: TaskType::LogToGitHub,
        payload: payload.clone(),
        scheduled_for: None,
        max_retries: 3,
    });

    // Task: PostSubstackNote (if enabled)
    let substack_task = if config.post_to_substack {
        Some(state.task_queue.create_task(CreateTaskRequest {
            task_type: TaskType::PostSubstackNote,
            payload: payload.clone(),
            scheduled_for: None,
            max_retries: 3,
        }))
    } else {
        None
    };

    // Task: PostTweet (if enabled)
    let twitter_task = if config.post_to_twitter {
        Some(state.task_queue.create_task(CreateTaskRequest {
            task_type: TaskType::PostTweet,
            payload: payload.clone(),
            scheduled_for: None,
            max_retries: 3,
        }))
    } else {
        None
    };

    // Task: PostLinkedIn (if enabled)
    let linkedin_task = if config.post_to_linkedin {
        Some(state.task_queue.create_task(CreateTaskRequest {
            task_type: TaskType::PostLinkedIn,
            payload: payload.clone(),
            scheduled_for: None,
            max_retries: 3,
        }))
    } else {
        None
    };

    let github_task_id = github_task.as_ref().ok().map(|t| t.id.clone());
    let substack_task_id = substack_task
        .as_ref()
        .and_then(|r| r.as_ref().ok())
        .map(|t| t.id.clone());
    let twitter_task_id = twitter_task
        .as_ref()
        .and_then(|r| r.as_ref().ok())
        .map(|t| t.id.clone());
    let linkedin_task_id = linkedin_task
        .as_ref()
        .and_then(|r| r.as_ref().ok())
        .map(|t| t.id.clone());
    let response_task_id = substack_task_id
        .clone()
        .or_else(|| twitter_task_id.clone())
        .or_else(|| linkedin_task_id.clone())
        .or_else(|| github_task_id.clone());
    let response_url = url.clone();
    let response_excerpt = excerpt.clone();

    // Spawn the entire pipeline in the background
    let state_clone = state.clone();
    tokio::spawn(async move {
        execute_bookmark_pipeline(
            state_clone,
            url,
            excerpt,
            notes,
            github_task_id,
            substack_task_id,
            twitter_task_id,
            linkedin_task_id,
        )
        .await;
    });

    // Return immediately
    (
        StatusCode::OK,
        Json(BookmarkResponse {
            success: true,
            task_id: response_task_id,
            url: Some(response_url),
            title: None,
            author: None,
            content_type: None,
            excerpt: response_excerpt,
            image_url: None,
            content: None,
            error: None,
        })
        .into_response(),
    )
}

async fn ghostpost_standalone_draft_handler(
    State(state): State<Arc<ServerState>>,
    Json(req): Json<GhostpostDraftRequest>,
) -> impl IntoResponse {
    let url = req.url.clone();

    let entry = match tokio::task::spawn_blocking({
        let url = url.clone();
        move || consumed_core::metadata::extract(&url)
    })
    .await
    {
        Ok(Ok(entry)) => entry,
        Ok(Err(e)) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(GhostpostDraftResponse {
                    success: false,
                    draft_id: None,
                    status: None,
                    username: None,
                    error: Some(format!("Failed to extract metadata: {}", e)),
                })
                .into_response(),
            );
        }
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(GhostpostDraftResponse {
                    success: false,
                    draft_id: None,
                    status: None,
                    username: None,
                    error: Some(format!("Metadata task join error: {}", e)),
                })
                .into_response(),
            );
        }
    };

    let title = entry.title.clone();
    let author = entry.author.clone();
    let content_type = entry.content_type.to_string();
    let image_url = entry.image_url.clone();
    let scraped_markdown = scrape_content(&url, &content_type).await;

    match crate::remote::create_standalone_draft(
        state.config.clone(),
        url.clone(),
        title.clone(),
        author.clone(),
        content_type.clone(),
        req.excerpt.clone(),
        req.notes.clone(),
        scraped_markdown,
        image_url.clone(),
    )
    .await
    {
        Ok(draft) => (
            StatusCode::OK,
            Json(GhostpostDraftResponse {
                success: true,
                draft_id: draft.draft_id,
                status: Some(draft.status),
                username: Some(draft.username),
                error: None,
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(GhostpostDraftResponse {
                success: false,
                draft_id: None,
                status: None,
                username: None,
                error: Some(e),
            })
            .into_response(),
        ),
    }
}

/// Run the full bookmark pipeline in the background:
/// metadata extraction → scrape → generate recommendation → execute tasks
async fn execute_bookmark_pipeline(
    state: Arc<ServerState>,
    url: String,
    excerpt: Option<String>,
    notes: Option<String>,
    github_task_id: Option<String>,
    substack_task_id: Option<String>,
    twitter_task_id: Option<String>,
    linkedin_task_id: Option<String>,
) {
    // Mark tasks as running
    for id in [
        &github_task_id,
        &substack_task_id,
        &twitter_task_id,
        &linkedin_task_id,
    ] {
        if let Some(ref id) = id {
            let _ = state
                .task_queue
                .update_task_status(id, TaskStatus::Running, None, None);
        }
    }

    // Step 1: Extract metadata
    let entry = match tokio::task::spawn_blocking({
        let url = url.clone();
        move || consumed_core::metadata::extract(&url)
    })
    .await
    {
        Ok(Ok(entry)) => entry,
        Ok(Err(e)) => {
            let err = format!("Failed to extract metadata: {}", e);
            error!("[bookmark] {}", err);
            for id in [
                &github_task_id,
                &substack_task_id,
                &twitter_task_id,
                &linkedin_task_id,
            ] {
                if let Some(ref id) = id {
                    let _ = state.task_queue.update_task_status(
                        id,
                        TaskStatus::Pending,
                        None,
                        Some(err.clone()),
                    );
                }
            }
            return;
        }
        Err(e) => {
            let err = format!("Metadata task join error: {}", e);
            error!("[bookmark] {}", err);
            for id in [
                &github_task_id,
                &substack_task_id,
                &twitter_task_id,
                &linkedin_task_id,
            ] {
                if let Some(ref id) = id {
                    let _ = state.task_queue.update_task_status(
                        id,
                        TaskStatus::Pending,
                        None,
                        Some(err.clone()),
                    );
                }
            }
            return;
        }
    };

    let title = entry.title.clone();
    let author = entry.author.clone();
    let content_type = entry.content_type.to_string();
    let image_url = entry.image_url.clone();

    // Step 2: Scrape content (best-effort)
    let scraped_markdown = scrape_content(&url, &content_type).await;

    // Step 3: Execute GitHub task
    if let Some(ref task_id) = github_task_id {
        let config = state.config.get();
        let token = config
            .github_token
            .or_else(|| env::var("GITHUB_TOKEN").ok());
        let repo = config.github_repo.or_else(|| env::var("GITHUB_REPO").ok());
        let diary_path = env::var("LOG_FILE")
            .ok()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| {
                if config.diary_path.is_empty() || config.diary_path == "reading_now.md" {
                    "reading_now.md".to_string()
                } else {
                    config.diary_path.clone()
                }
            });

        if let (Some(token), Some(repo)) = (token, repo) {
            execute_github_task(&state, task_id, &url, &repo, &diary_path, &token).await;
        } else {
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::Pending,
                None,
                Some("Missing GITHUB_TOKEN or GITHUB_REPO".to_string()),
            );
        }
    }

    // Step 4: Generate recommendation and post to enabled platforms
    let posting_needed =
        substack_task_id.is_some() || twitter_task_id.is_some() || linkedin_task_id.is_some();
    if posting_needed {
        match generate_recommendation(
            &url,
            &title,
            author.as_deref(),
            &content_type,
            excerpt.as_deref(),
            scraped_markdown.as_deref(),
            notes.as_deref(),
        )
        .await
        {
            Ok(rec) => {
                // Save generated content into each task's payload so retries don't need to re-generate
                for task_id in [&substack_task_id, &twitter_task_id, &linkedin_task_id] {
                    if let Some(ref id) = task_id {
                        if let Ok(Some(task)) = state.task_queue.get_task(id) {
                            let mut payload = task.payload.clone();
                            if let Some(obj) = payload.as_object_mut() {
                                obj.insert(
                                    "content".to_string(),
                                    serde_json::Value::String(rec.content.clone()),
                                );
                                if let Some(ref img) = image_url {
                                    obj.insert(
                                        "image_url".to_string(),
                                        serde_json::Value::String(img.clone()),
                                    );
                                }
                            }
                            let _ = state.task_queue.update_task_payload(id, payload);
                        }
                    }
                }

                // Substack and LinkedIn get the URL appended to the content
                let content_with_url = format!("{}\n\n{}", rec.content, rec.url);

                if let Some(ref task_id) = substack_task_id {
                    execute_substack_task(&state, task_id, &content_with_url, image_url.as_deref())
                        .await;
                }
                if let Some(ref task_id) = twitter_task_id {
                    // Twitter gets the URL as a separate reply in the thread
                    execute_twitter_task(
                        &state,
                        task_id,
                        &rec.content,
                        image_url.as_deref(),
                        Some(&rec.url),
                    )
                    .await;
                }
                if let Some(ref task_id) = linkedin_task_id {
                    execute_linkedin_task(&state, task_id, &content_with_url, image_url.as_deref())
                        .await;
                }
            }
            Err(e) => {
                error!("[bookmark] Failed to generate recommendation: {}", e);
                let err_msg = Some(format!("Failed to generate recommendation: {}", e));
                for id in [&substack_task_id, &twitter_task_id, &linkedin_task_id] {
                    if let Some(ref id) = id {
                        let _ = state.task_queue.update_task_status(
                            id,
                            TaskStatus::Pending,
                            None,
                            err_msg.clone(),
                        );
                    }
                }
            }
        }
    }
}

/// Execute GitHub logging task in background
async fn execute_github_task(
    state: &Arc<ServerState>,
    task_id: &str,
    url: &str,
    repo: &str,
    diary_path: &str,
    token: &str,
) {
    // Mark as running
    let _ = state
        .task_queue
        .update_task_status(task_id, TaskStatus::Running, None, None);

    // Execute GitHub commit
    let url = url.to_string();
    let repo = repo.to_string();
    let diary_path = diary_path.to_string();
    let token = token.to_string();

    let result = tokio::task::spawn_blocking(move || {
        consumed_core::github::add_entry_to_github_with_date(&url, &repo, &diary_path, &token, None)
    })
    .await;

    match result {
        Ok(Ok(_)) => {
            // Success - mark completed
            let _ = state
                .task_queue
                .update_task_status(task_id, TaskStatus::Completed, None, None);
        }
        Ok(Err(e)) => {
            // Failure - keep pending with error for manual retry
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::Pending,
                None,
                Some(e.to_string()),
            );
        }
        Err(e) => {
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::Pending,
                None,
                Some(format!("Task join error: {}", e)),
            );
        }
    }
}

/// Execute Substack note posting task via Python CDP script
async fn execute_substack_task(
    state: &Arc<ServerState>,
    task_id: &str,
    content: &str,
    image_url: Option<&str>,
) {
    let _ = state
        .task_queue
        .update_task_status(task_id, TaskStatus::Running, None, None);

    let content = content.to_string();
    let image_url = image_url.map(|s| s.to_string());
    let python_dir = get_python_project_dir();
    let script = python_dir.join("tasks").join("substack_notes.py");

    let result = tokio::task::spawn_blocking(move || {
        let mut cmd = std::process::Command::new("uv");
        cmd.arg("run")
            .arg("--project")
            .arg(&python_dir)
            .arg("python")
            .arg(&script)
            .arg(&content);

        if let Some(ref img) = image_url {
            cmd.arg("--image").arg(img);
        }

        cmd.output()
    })
    .await;

    match result {
        Ok(Ok(output)) if output.status.success() => {
            let _ = state.task_queue.delete_task(task_id);
        }
        Ok(Ok(output)) if output.status.code() == Some(2) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::AuthRequired,
                None,
                Some(format!("Substack post failed: {}", stderr)),
            );
            send_auth_notification("Substack");
        }
        Ok(Ok(output)) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Substack post failed: {}", stderr);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Ok(Err(e)) => {
            error!("Failed to spawn substack process: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Err(e) => {
            error!("Substack task join error: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
    }
}

/// Execute Twitter posting task via Python CDP script
async fn execute_twitter_task(
    state: &Arc<ServerState>,
    task_id: &str,
    content: &str,
    image_url: Option<&str>,
    link_url: Option<&str>,
) {
    let _ = state
        .task_queue
        .update_task_status(task_id, TaskStatus::Running, None, None);

    let content = content.to_string();
    let image_url = image_url.map(|s| s.to_string());
    let link_url = link_url.map(|s| s.to_string());
    let python_dir = get_python_project_dir();
    let script = python_dir.join("tasks").join("twitter_post.py");

    let result = tokio::task::spawn_blocking(move || {
        let mut cmd = std::process::Command::new("uv");
        cmd.arg("run")
            .arg("--project")
            .arg(&python_dir)
            .arg("python")
            .arg(&script)
            .arg(&content);

        if let Some(ref img) = image_url {
            cmd.arg("--image").arg(img);
        }

        if let Some(ref link) = link_url {
            cmd.arg("--url").arg(link);
        }

        cmd.output()
    })
    .await;

    match result {
        Ok(Ok(output)) if output.status.success() => {
            let _ = state.task_queue.delete_task(task_id);
        }
        Ok(Ok(output)) if output.status.code() == Some(2) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::AuthRequired,
                None,
                Some(format!("Twitter post failed: {}", stderr)),
            );
            send_auth_notification("Twitter");
        }
        Ok(Ok(output)) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Twitter post failed: {}", stderr);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Ok(Err(e)) => {
            error!("Failed to spawn twitter process: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Err(e) => {
            error!("Twitter task join error: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
    }
}

/// Execute LinkedIn posting task via Python CDP script
async fn execute_linkedin_task(
    state: &Arc<ServerState>,
    task_id: &str,
    content: &str,
    image_url: Option<&str>,
) {
    let _ = state
        .task_queue
        .update_task_status(task_id, TaskStatus::Running, None, None);

    let content = content.to_string();
    let image_url = image_url.map(|s| s.to_string());
    let python_dir = get_python_project_dir();
    let script = python_dir.join("tasks").join("linkedin_post.py");

    let result = tokio::task::spawn_blocking(move || {
        let mut cmd = std::process::Command::new("uv");
        cmd.arg("run")
            .arg("--project")
            .arg(&python_dir)
            .arg("python")
            .arg(&script)
            .arg(&content);

        if let Some(ref img) = image_url {
            cmd.arg("--image").arg(img);
        }

        cmd.output()
    })
    .await;

    match result {
        Ok(Ok(output)) if output.status.success() => {
            let _ = state.task_queue.delete_task(task_id);
        }
        Ok(Ok(output)) if output.status.code() == Some(2) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::AuthRequired,
                None,
                Some(format!("LinkedIn post failed: {}", stderr)),
            );
            send_auth_notification("LinkedIn");
        }
        Ok(Ok(output)) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("LinkedIn post failed: {}", stderr);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Ok(Err(e)) => {
            error!("Failed to spawn linkedin process: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
        Err(e) => {
            error!("LinkedIn task join error: {}", e);
            if let Ok(false) = state.task_queue.increment_retry(task_id) {
                let _ = state.task_queue.delete_task(task_id);
            }
        }
    }
}

async fn execute_reddit_research_task(
    state: &Arc<ServerState>,
    task_id: &str,
    request: RedditResearchRequest,
) {
    let _ = state
        .task_queue
        .update_task_status(task_id, TaskStatus::Running, None, None);

    #[cfg(target_os = "macos")]
    if let Err(e) = crate::browser::ensure_cdp() {
        let _ = state.task_queue.update_task_status(
            task_id,
            TaskStatus::Pending,
            None,
            Some(format!("CDP setup failed: {}", e)),
        );
        return;
    }

    match research_reddit_via_cdp(request).await {
        Ok(result) => {
            let findings_summary = summarize_findings(&result.findings);
            let result_value = serde_json::json!({
                "query": result.query,
                "attempted_queries": result.attempted_queries,
                "adequately_answered": result.adequately_answered,
                "unique_post_count": result.unique_post_count,
                "relevant_comment_count": result.relevant_comment_count,
                "summary": findings_summary,
                "findings": result.findings,
            });
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::Completed,
                Some(result_value),
                None,
            );
        }
        Err(e) => {
            error!("[reddit_research] task {} failed: {}", task_id, e);
            match state.task_queue.increment_retry(task_id) {
                Ok(true) => {
                    let _ = state.task_queue.update_task_status(
                        task_id,
                        TaskStatus::Pending,
                        None,
                        Some(e),
                    );
                }
                Ok(false) => {
                    let _ = state.task_queue.update_task_status(
                        task_id,
                        TaskStatus::Failed,
                        None,
                        Some(e),
                    );
                }
                Err(update_err) => {
                    let _ = state.task_queue.update_task_status(
                        task_id,
                        TaskStatus::Failed,
                        None,
                        Some(format!(
                            "Research failed and retry update failed: {} (original: {})",
                            update_err, e
                        )),
                    );
                }
            }
        }
    }
}

fn required_payload_string(payload: &serde_json::Value, key: &str) -> Option<String> {
    payload
        .get(key)
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToOwned::to_owned)
}

async fn dispatch_task(
    state: &Arc<ServerState>,
    task_id: &str,
    task_type: TaskType,
    payload: &serde_json::Value,
) {
    match task_type {
        TaskType::PostSubstackNote => {
            let Some(content) = required_payload_string(payload, "content") else {
                let _ = state.task_queue.update_task_status(
                    task_id,
                    TaskStatus::Failed,
                    None,
                    Some("Missing content for post_substack task".to_string()),
                );
                return;
            };
            let url = required_payload_string(payload, "url");
            let image_url = required_payload_string(payload, "image_url");
            let content_with_url = if let Some(ref url) = url {
                format!("{}\n\n{}", content, url)
            } else {
                content.clone()
            };
            execute_substack_task(state, task_id, &content_with_url, image_url.as_deref()).await;
        }
        TaskType::PostTweet => {
            let Some(content) = required_payload_string(payload, "content") else {
                let _ = state.task_queue.update_task_status(
                    task_id,
                    TaskStatus::Failed,
                    None,
                    Some("Missing content for post_x task".to_string()),
                );
                return;
            };
            let url = required_payload_string(payload, "url");
            let image_url = required_payload_string(payload, "image_url");
            execute_twitter_task(state, task_id, &content, image_url.as_deref(), url.as_deref()).await;
        }
        TaskType::PostLinkedIn => {
            let Some(content) = required_payload_string(payload, "content") else {
                let _ = state.task_queue.update_task_status(
                    task_id,
                    TaskStatus::Failed,
                    None,
                    Some("Missing content for post_linkedin task".to_string()),
                );
                return;
            };
            let url = required_payload_string(payload, "url");
            let image_url = required_payload_string(payload, "image_url");
            let content_with_url = if let Some(ref url) = url {
                format!("{}\n\n{}", content, url)
            } else {
                content.clone()
            };
            execute_linkedin_task(state, task_id, &content_with_url, image_url.as_deref()).await;
        }
        TaskType::ResearchReddit => match RedditResearchRequest::from_payload(payload) {
            Ok(req) => execute_reddit_research_task(state, task_id, req).await,
            Err(e) => {
                let _ =
                    state
                        .task_queue
                        .update_task_status(task_id, TaskStatus::Failed, None, Some(e));
            }
        },
        _ => {
            let _ = state.task_queue.update_task_status(
                task_id,
                TaskStatus::Failed,
                None,
                Some(format!(
                    "Task type '{}' is queued but dispatcher is not implemented yet in consumed-daemon",
                    task_type.as_str()
                )),
            );
            warn!(
                "[dispatch] queued task type '{}' but no dispatcher implementation exists yet",
                task_type.as_str()
            );
        }
    }
}

/// Get the path to the Python scripts directory
fn get_python_project_dir() -> std::path::PathBuf {
    // Check CONSUMED_PYTHON_DIR env var first
    if let Ok(dir) = env::var("CONSUMED_PYTHON_DIR") {
        return std::path::PathBuf::from(dir);
    }

    // Prefer core python project path from tauri/
    let candidate = std::path::PathBuf::from("../tools/python");
    if candidate.exists() {
        return candidate;
    }

    std::path::PathBuf::from("python")
}

fn get_scrapers_dir() -> std::path::PathBuf {
    if let Ok(core_dir) = env::var("CONSUMED_CORE_DIR") {
        return std::path::PathBuf::from(core_dir).join("scrapers");
    }

    let candidate = std::path::PathBuf::from("../tools/scrapers");
    if candidate.exists() {
        return candidate;
    }

    std::path::PathBuf::from("scrapers")
}

/// Scrape content using Python unified scraper
async fn scrape_content(url: &str, content_type: &str) -> Option<String> {
    let input = serde_json::json!({
        "url": url,
        "content_type": content_type,
    });

    let input_str = input.to_string();
    let python_dir = get_python_project_dir();
    let scraper_script = get_scrapers_dir().join("scrape.py");

    let output = match tokio::task::spawn_blocking(move || {
        std::process::Command::new("uv")
            .arg("run")
            .arg("--project")
            .arg(&python_dir)
            .arg("python")
            .arg(&scraper_script)
            .arg(&input_str)
            .output()
    })
    .await
    {
        Ok(Ok(output)) => output,
        Ok(Err(e)) => {
            error!("Failed to spawn scrape process: {}", e);
            return None;
        }
        Err(e) => {
            error!("Scrape task join error: {}", e);
            return None;
        }
    };

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        error!("Scrape script failed: {}", stderr);
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = match serde_json::from_str(&stdout) {
        Ok(v) => v,
        Err(e) => {
            error!(
                "Failed to parse scrape output: {} - output was: {}",
                e, stdout
            );
            return None;
        }
    };

    parsed
        .get("markdown")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// Generate recommendation using Python LLM script
/// Generated recommendation with content and source URL separated.
struct GeneratedRecommendation {
    content: String,
    url: String,
}

async fn generate_recommendation(
    url: &str,
    title: &str,
    author: Option<&str>,
    content_type: &str,
    excerpt: Option<&str>,
    scraped_content: Option<&str>,
    notes: Option<&str>,
) -> Result<GeneratedRecommendation, String> {
    let input = serde_json::json!({
        "url": url,
        "title": title,
        "author": author,
        "content_type": content_type,
        "excerpt": excerpt,
        "scraped_content": scraped_content,
        "notes": notes,
    });

    let input_str = input.to_string();
    let python_dir = get_python_project_dir();
    let script = python_dir.join("tasks").join("generate.py");

    let output = tokio::task::spawn_blocking(move || {
        std::process::Command::new("uv")
            .arg("run")
            .arg("--project")
            .arg(&python_dir)
            .arg("python")
            .arg(&script)
            .arg(&input_str)
            .output()
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
    .map_err(|e| format!("Failed to spawn process: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Generation script failed: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&stdout).map_err(|e| {
        format!(
            "Failed to parse generation output: {} - output was: {}",
            e, stdout
        )
    })?;

    if let Some(error) = parsed.get("error").and_then(|e| e.as_str()) {
        return Err(format!("Generation error: {}", error));
    }

    let content = parsed
        .get("content")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| "No content in generation response".to_string())?;

    let url = parsed
        .get("url")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| "No url in generation response".to_string())?;

    Ok(GeneratedRecommendation { content, url })
}

/// Confirm Substack post completion
async fn confirm_substack_post_handler(
    State(state): State<Arc<ServerState>>,
    Json(req): Json<ConfirmSubstackPostRequest>,
) -> impl IntoResponse {
    let task_id = &req.task_id;

    // Check if task exists
    match state.task_queue.get_task(task_id) {
        Ok(Some(_)) => {}
        Ok(None) => {
            return (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse {
                    success: false,
                    error: "Task not found".to_string(),
                })
                .into_response(),
            );
        }
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    success: false,
                    error: e,
                })
                .into_response(),
            );
        }
    }

    match req.status.as_str() {
        "completed" => {
            if let Err(e) =
                state
                    .task_queue
                    .update_task_status(task_id, TaskStatus::Completed, None, None)
            {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(ErrorResponse {
                        success: false,
                        error: e,
                    })
                    .into_response(),
                );
            }
            (
                StatusCode::OK,
                Json(serde_json::json!({ "success": true })).into_response(),
            )
        }
        "failed" => {
            // Keep task pending with error message for manual retry later
            let _ =
                state
                    .task_queue
                    .update_task_status(task_id, TaskStatus::Pending, None, req.error);
            (
                StatusCode::OK,
                Json(serde_json::json!({ "success": true })).into_response(),
            )
        }
        _ => (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                success: false,
                error: "Invalid status. Use 'completed' or 'failed'".to_string(),
            })
            .into_response(),
        ),
    }
}

/// Get pending tasks (ready to execute)
async fn get_pending_tasks_handler(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
    match state.task_queue.get_pending_tasks() {
        Ok(tasks) => (
            StatusCode::OK,
            Json(TaskListResponse {
                success: true,
                tasks,
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Get all tasks with optional status filter
async fn get_tasks_handler(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
    match state.task_queue.get_tasks(None) {
        Ok(tasks) => (
            StatusCode::OK,
            Json(TaskListResponse {
                success: true,
                tasks,
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

async fn get_supported_tasks_handler() -> Json<SupportedTasksResponse> {
    Json(SupportedTasksResponse {
        success: true,
        commands: supported_task_commands(),
    })
}

/// Create a new task
/// Enqueue one or more tasks by user-facing command name.
/// Use GET /supported-tasks for the centralized list.
async fn enqueue_handler(
    State(state): State<Arc<ServerState>>,
    Json(req): Json<EnqueueRequest>,
) -> impl IntoResponse {
    if !AVAILABLE_COMMANDS.contains(&req.task.as_str()) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "success": false,
                "error": format!("Unknown task '{}'. Available: {}", req.task, AVAILABLE_COMMANDS.join(", ")),
            }))
            .into_response(),
        );
    }

    let payload = serde_json::json!({
        "url": req.url,
        "content": req.content,
        "image_url": req.image_url,
        "query": req.query,
    });

    let task_types = match resolve_command_to_task_types(req.task.as_str()) {
        Some(types) => types,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "success": false,
                    "error": format!("Task '{}' is not mapped in command resolver", req.task),
                }))
                .into_response(),
            );
        }
    };

    let mut created: Vec<(String, TaskType)> = Vec::new();
    for task_type in task_types {
        match state.task_queue.create_task(CreateTaskRequest {
            task_type: task_type.clone(),
            payload: payload.clone(),
            scheduled_for: None,
            max_retries: 3,
        }) {
            Ok(task) => created.push((task.id, task_type)),
            Err(e) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(serde_json::json!({ "success": false, "error": e })).into_response(),
                );
            }
        }
    }

    let task_ids: Vec<String> = created.iter().map(|(id, _)| id.clone()).collect();

    // Attempt immediately in the background
    let state_clone = state.clone();
    let payload_for_dispatch = payload.clone();
    tokio::spawn(async move {
        for (task_id, task_type) in created {
            dispatch_task(&state_clone, &task_id, task_type, &payload_for_dispatch).await;
        }
    });

    (
        StatusCode::CREATED,
        Json(serde_json::json!({ "success": true, "task_ids": task_ids })).into_response(),
    )
}

async fn create_task_handler(
    State(state): State<Arc<ServerState>>,
    Json(req): Json<CreateTaskRequest>,
) -> impl IntoResponse {
    match state.task_queue.create_task(req) {
        Ok(task) => (
            StatusCode::CREATED,
            Json(TaskResponse {
                success: true,
                task: Some(task),
                message: Some("Task created".to_string()),
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Get a single task by ID
async fn get_task_handler(
    State(state): State<Arc<ServerState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    match state.task_queue.get_task(&id) {
        Ok(Some(task)) => (
            StatusCode::OK,
            Json(TaskResponse {
                success: true,
                task: Some(task),
                message: None,
            })
            .into_response(),
        ),
        Ok(None) => (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                success: false,
                error: "Task not found".to_string(),
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Update a task's status
async fn update_task_handler(
    State(state): State<Arc<ServerState>>,
    Path(id): Path<String>,
    Json(req): Json<UpdateTaskRequest>,
) -> impl IntoResponse {
    // First check if task exists
    match state.task_queue.get_task(&id) {
        Ok(Some(_)) => {}
        Ok(None) => {
            return (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse {
                    success: false,
                    error: "Task not found".to_string(),
                })
                .into_response(),
            );
        }
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    success: false,
                    error: e,
                })
                .into_response(),
            );
        }
    }

    // Update the task if status provided
    if let Some(status) = req.status {
        if let Err(e) = state
            .task_queue
            .update_task_status(&id, status, req.result, req.error)
        {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    success: false,
                    error: e,
                })
                .into_response(),
            );
        }
    }

    // Return updated task
    match state.task_queue.get_task(&id) {
        Ok(task) => (
            StatusCode::OK,
            Json(TaskResponse {
                success: true,
                task,
                message: Some("Task updated".to_string()),
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Delete a task
async fn delete_task_handler(
    State(state): State<Arc<ServerState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    match state.task_queue.delete_task(&id) {
        Ok(true) => (
            StatusCode::OK,
            Json(TaskResponse {
                success: true,
                task: None,
                message: Some("Task deleted".to_string()),
            })
            .into_response(),
        ),
        Ok(false) => (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                success: false,
                error: "Task not found".to_string(),
            })
            .into_response(),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                success: false,
                error: e,
            })
            .into_response(),
        ),
    }
}

/// Scrape endpoint — scrape content from a URL and return markdown
async fn scrape_handler(
    State(_state): State<Arc<ServerState>>,
    Json(req): Json<ScrapeRequest>,
) -> impl IntoResponse {
    let url = req.url.clone();

    // Step 1: Detect content type from URL (no HTTP request)
    let content_type = consumed_core::metadata::detect_content_type(&url);
    let content_type_str = content_type.to_string();

    // Step 2: Run metadata extraction and Python scraping in parallel (if scraper exists)
    let metadata_future = {
        let url_clone = url.clone();
        tokio::task::spawn_blocking(move || consumed_core::metadata::extract(&url_clone))
    };

    let scraper_future = if content_type.has_scraper() {
        let input = serde_json::json!({
            "url": &url,
            "content_type": &content_type_str,
            "startTime": req.start_time,
            "endTime": req.end_time,
            "downloadVideo": req.download_video,
            "downloadAudio": req.download_audio,
            "downloadTranscript": req.download_transcript,
            "openaiApiKey": req.openai_api_key,
        });
        let input_str = input.to_string();
        let python_dir = get_python_project_dir();
        let scraper_script = get_scrapers_dir().join("scrape.py");

        Some(tokio::task::spawn_blocking(move || {
            std::process::Command::new("uv")
                .arg("run")
                .arg("--project")
                .arg(&python_dir)
                .arg("python")
                .arg(&scraper_script)
                .arg(&input_str)
                .output()
        }))
    } else {
        None
    };

    // Await both concurrently
    let (metadata_result, scraper_result) = if let Some(scraper_fut) = scraper_future {
        let (meta, scrape) = tokio::join!(metadata_future, scraper_fut);
        (meta, Some(scrape))
    } else {
        let meta = metadata_future.await;
        (meta, None)
    };

    // Process metadata result
    let mut entry = match metadata_result {
        Ok(Ok(entry)) => entry,
        Ok(Err(e)) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ScrapeResponse {
                    success: false,
                    markdown: None,
                    filename: None,
                    content_type: None,
                    title: None,
                    author: None,
                    director: None,
                    year: None,
                    starring: None,
                    error: Some(format!("Failed to extract metadata: {}", e)),
                    audio_data: None,
                    audio_filename: None,
                    audio_mime_type: None,
                    video_data: None,
                    video_filename: None,
                    video_mime_type: None,
                })
                .into_response(),
            );
        }
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ScrapeResponse {
                    success: false,
                    markdown: None,
                    filename: None,
                    content_type: None,
                    title: None,
                    author: None,
                    director: None,
                    year: None,
                    starring: None,
                    error: Some(format!("Task error: {}", e)),
                    audio_data: None,
                    audio_filename: None,
                    audio_mime_type: None,
                    video_data: None,
                    video_filename: None,
                    video_mime_type: None,
                })
                .into_response(),
            );
        }
    };

    // Process scraper result
    let (scraped_markdown, filename, first_tweet, audio_data, audio_filename, audio_mime_type, video_data, video_filename, video_mime_type) = match scraper_result {
        Some(Ok(Ok(output))) if output.status.success() => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            match serde_json::from_str::<serde_json::Value>(&stdout) {
                Ok(parsed) => {
                    let md = parsed
                        .get("markdown")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());
                    let fname = parsed
                        .get("filename")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());
                    let ft = parsed
                        .get("first_tweet")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());
                    let ad = parsed.get("audioData").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let af = parsed.get("audioFilename").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let am = parsed.get("audioMimeType").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let vd = parsed.get("videoData").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let vf = parsed.get("videoFilename").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let vm = parsed.get("videoMimeType").and_then(|v| v.as_str()).map(|s| s.to_string());
                    (md, fname, ft, ad, af, am, vd, vf, vm)
                }
                Err(_) => (None, None, None, None, None, None, None, None, None),
            }
        }
        _ => (None, None, None, None, None, None, None, None, None),
    };

    // For tweets, build title from handle + first tweet text
    if content_type == consumed_core::models::ContentType::Tweet {
        if let Some(ref ft) = first_tweet {
            // Extract handle from URL path: /handle/status/id
            let handle = url
                .trim_start_matches("https://")
                .trim_start_matches("http://")
                .split('/')
                .nth(1) // skip host, get first path segment
                .filter(|s| !s.is_empty());
            if let Some(handle) = handle {
                let words: Vec<&str> = ft.split_whitespace().take(5).collect();
                let preview = words.join(" ");
                entry.title = format!("@{}: {}...", handle, preview);
            }
        }
    }

    let title = entry.title.clone();
    let author = entry.author.clone();
    let director = entry.director.clone();
    let year = entry.year;
    let starring = entry.starring.clone();
    // Prefer URL-detected content type when extractor returns Unknown
    let final_content_type = if entry.content_type == consumed_core::models::ContentType::Unknown {
        content_type_str.clone()
    } else {
        entry.content_type.to_string()
    };

    // Step 3: Build metadata header and combine with scraped content
    let header = consumed_core::metadata::header::format_metadata_header(&entry);

    let final_markdown = if let Some(scraped_md) = scraped_markdown {
        match header {
            Some(h) => Some(format!("{}\n\n---\n\n{}", h, scraped_md)),
            None => Some(scraped_md),
        }
    } else {
        None
    };

    (
        StatusCode::OK,
        Json(ScrapeResponse {
            success: true,
            markdown: final_markdown,
            filename,
            content_type: Some(final_content_type),
            title: Some(title),
            author,
            director,
            year,
            starring,
            error: None,
            audio_data,
            audio_filename,
            audio_mime_type,
            video_data,
            video_filename,
            video_mime_type,
        })
        .into_response(),
    )
}

/// Send a macOS notification when a platform requires login
fn send_auth_notification(platform: &str) {
    let msg = format!(
        "Log in to {} in Chrome, then click \\\"Retry Logins\\\" in the menu bar.",
        platform
    );
    let script = format!("display notification \"{}\" with title \"Consumed\"", msg);
    let _ = std::process::Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .spawn();
}

/// Background loop: retry AuthRequired tasks once per hour with random spacing
async fn retry_auth_loop(state: Arc<ServerState>) {
    use rand::Rng;

    loop {
        tokio::time::sleep(std::time::Duration::from_secs(10800)).await; // 3 hours

        let mut tasks = match state.task_queue.get_tasks(Some(TaskStatus::Pending)) {
            Ok(t) => t,
            Err(e) => {
                error!("[retry] Failed to query pending tasks: {}", e);
                vec![]
            }
        };

        match state.task_queue.get_tasks(Some(TaskStatus::AuthRequired)) {
            Ok(t) => tasks.extend(t),
            Err(e) => error!("[retry] Failed to query auth-required tasks: {}", e),
        };

        if tasks.is_empty() {
            continue;
        }

        info!("[retry] Retrying {} queued tasks", tasks.len());

        for task in tasks {
            // Random delay between 10–120 seconds to avoid bot detection
            let delay = rand::rng().random_range(10..=120);
            tokio::time::sleep(std::time::Duration::from_secs(delay)).await;

            dispatch_task(&state, &task.id, task.task_type, &task.payload).await;
        }
    }
}

/// Create the router with all endpoints
pub fn create_router(state: Arc<ServerState>) -> Router {
    // CORS layer to allow extension requests from any origin
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        .route("/", get(health))
        .route("/health", get(health))
        .route("/import-cookies", post(import_cookies_handler))
        .route("/bookmark", post(bookmark_handler))
        .route("/ghostpost/standalone-draft", post(ghostpost_standalone_draft_handler))
        .route("/scrape", post(scrape_handler))
        .route(
            "/confirm-substack-post",
            post(confirm_substack_post_handler),
        )
        .route("/enqueue", post(enqueue_handler))
        .route("/supported-tasks", get(get_supported_tasks_handler))
        // Task queue endpoints
        .route("/tasks", get(get_tasks_handler))
        .route("/tasks", post(create_task_handler))
        .route("/tasks/pending", get(get_pending_tasks_handler))
        .route("/tasks/:id", get(get_task_handler))
        .route("/tasks/:id", patch(update_task_handler))
        .route("/tasks/:id", delete(delete_task_handler))
        .layer(cors)
        .with_state(state)
}

/// Start the server in a background task
pub async fn start_server(
    config: Arc<ConfigState>,
    mut shutdown_rx: oneshot::Receiver<()>,
) -> Result<(), String> {
    let port = config.get().port;
    let addr = SocketAddr::from(([127, 0, 0, 1], port));

    // Initialize task queue with SQLite
    let task_queue = TaskQueue::new(TaskQueue::default_db_path())?;
    info!(
        "Task queue initialized at {:?}",
        TaskQueue::default_db_path()
    );

    let state = Arc::new(ServerState { config, task_queue });

    // Spawn hourly retry loop for AuthRequired tasks
    tokio::spawn(retry_auth_loop(Arc::clone(&state)));

    let router = create_router(state);

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .map_err(|e| format!("Failed to bind to port {}: {}", port, e))?;

    info!("Server listening on http://{}", addr);

    axum::serve(listener, router)
        .with_graceful_shutdown(async move {
            let _ = (&mut shutdown_rx).await;
            info!("Server shutting down...");
        })
        .await
        .map_err(|e| format!("Server error: {}", e))?;

    Ok(())
}
