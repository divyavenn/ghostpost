//! Consumed Daemon - Tauri desktop app with embedded server.
//!
//! Runs as a system tray application, receives cookies from Chrome extension,
//! and provides a settings window.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod browser;
mod config;
mod cookies;
mod reddit_research;
mod remote;
mod server;
mod tasks;
mod tray;

use config::{Config, ConfigState};
use std::path::PathBuf;
use std::sync::Arc;
use tauri::Manager;
use tauri_plugin_autostart::MacosLauncher;
use tokio::sync::oneshot;
use tracing::{error, info};

fn init_logging() {
    let log_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("consumed");
    std::fs::create_dir_all(&log_dir).ok();

    let file_appender = tracing_appender::rolling::never(&log_dir, "daemon.log");
    let (non_blocking, guard) = tracing_appender::non_blocking(file_appender);

    tracing_subscriber::fmt()
        .with_writer(non_blocking)
        .with_target(false)
        .init();

    // Leak the guard so it lives for the entire process lifetime
    Box::leak(Box::new(guard));
}

/// Tauri commands for settings window

#[tauri::command]
fn get_config(state: tauri::State<Arc<ConfigState>>) -> Config {
    state.get()
}

#[tauri::command]
fn save_config(
    state: tauri::State<Arc<ConfigState>>,
    port: u16,
    auto_start: bool,
    github_token: Option<String>,
    github_repo: Option<String>,
    diary_path: String,
    post_to_substack: bool,
    post_to_twitter: bool,
    post_to_linkedin: bool,
    post_to_github: bool,
    ghostpost_api_base_url: String,
) -> Result<(), String> {
    state.update(|config| {
        config.port = port;
        config.auto_start = auto_start;
        config.github_token = github_token;
        config.github_repo = github_repo;
        config.diary_path = diary_path;
        config.post_to_substack = post_to_substack;
        config.post_to_twitter = post_to_twitter;
        config.post_to_linkedin = post_to_linkedin;
        config.post_to_github = post_to_github;
        config.ghostpost_api_base_url = ghostpost_api_base_url.trim_end_matches('/').to_string();
    })
}

#[tauri::command]
fn get_cookies_path() -> String {
    cookies::get_combined_state_path()
        .to_string_lossy()
        .to_string()
}

#[tauri::command]
async fn pair_device(
    state: tauri::State<'_, Arc<ConfigState>>,
    pair_code: String,
    device_name: Option<String>,
    machine_id: Option<String>,
) -> Result<Config, String> {
    remote::pair_device(state.inner().clone(), pair_code, device_name, machine_id).await
}

#[tauri::command]
async fn refresh_remote_state(
    state: tauri::State<'_, Arc<ConfigState>>,
) -> Result<remote::RemoteSyncResponse, String> {
    remote::refresh_remote_state(state.inner().clone()).await
}

fn main() {
    init_logging();

    // Load .env file (ignore if not found)
    dotenvy::dotenv().ok();

    #[cfg(target_os = "macos")]
    {
        match browser::ensure_cdp() {
            Ok(msg) => info!("[daemon] CDP: {}", msg),
            Err(e) => error!("[daemon] CDP setup failed: {}", e),
        }
    }

    // Create shared config state
    let config_state = Arc::new(ConfigState::new());
    let config_for_server = Arc::clone(&config_state);

    // Create shutdown channel for server
    let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();

    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--hidden"]),
        ))
        .manage(config_state)
        .invoke_handler(tauri::generate_handler![
            get_config,
            save_config,
            get_cookies_path,
            pair_device,
            refresh_remote_state,
        ])
        .setup(move |app| {
            // Set up system tray
            tray::setup_tray(app.handle())?;

            // Spawn the Axum server in a background task
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = server::start_server(config_for_server, shutdown_rx).await {
                    error!("Server error: {}", e);
                    app_handle.exit(1);
                }
            });

            // Hide the main window by default (runs in tray)
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            // Hide window instead of closing (keep running in tray)
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");

    // Signal server to shut down
    let _ = shutdown_tx.send(());
}
