//! Configuration management for the daemon.

use directories::ProjectDirs;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::RwLock;

/// Application configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Port for the local server (default: 9876)
    #[serde(default = "default_port")]
    pub port: u16,

    /// Auto-start on boot
    #[serde(default)]
    pub auto_start: bool,

    /// GitHub personal access token
    #[serde(default)]
    pub github_token: Option<String>,

    /// GitHub repository (owner/repo format)
    #[serde(default)]
    pub github_repo: Option<String>,

    /// Path to diary file in repo
    #[serde(default = "default_diary_path")]
    pub diary_path: String,

    /// Post to Substack Notes (default: true)
    #[serde(default = "default_true")]
    pub post_to_substack: bool,

    /// Post to Twitter/X (default: false)
    #[serde(default)]
    pub post_to_twitter: bool,

    /// Post to LinkedIn (default: false)
    #[serde(default)]
    pub post_to_linkedin: bool,

    /// Post to GitHub diary file (default: false)
    #[serde(default)]
    pub post_to_github: bool,

    /// Ghostpost backend base URL (without trailing slash)
    #[serde(default = "default_ghostpost_api_base_url")]
    pub ghostpost_api_base_url: String,

    /// Daemon auth token returned from /desktop/pairing/complete
    #[serde(default)]
    pub daemon_token: Option<String>,

    /// Paired device ID assigned by backend
    #[serde(default)]
    pub paired_device_id: Option<String>,

    /// Ghostpost user metadata for settings display
    #[serde(default)]
    pub paired_user_id: Option<String>,
    #[serde(default)]
    pub paired_user_email: Option<String>,
    #[serde(default)]
    pub paired_twitter_handle: Option<String>,

    /// Selected platforms for daemon account checks
    #[serde(default = "default_platforms")]
    pub platform_preferences: Vec<String>,

    /// Last synced logged-in account status by platform
    #[serde(default)]
    pub linked_accounts: HashMap<String, PlatformAccountState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PlatformAccountState {
    #[serde(default = "default_unknown")]
    pub status: String,
    #[serde(default)]
    pub account: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

fn default_port() -> u16 {
    9876
}

fn default_diary_path() -> String {
    "reading_now.md".to_string()
}

fn default_true() -> bool {
    true
}

fn default_ghostpost_api_base_url() -> String {
    "http://localhost:8000".to_string()
}

fn default_platforms() -> Vec<String> {
    vec!["twitter".to_string()]
}

fn default_unknown() -> String {
    "unknown".to_string()
}

impl Default for Config {
    fn default() -> Self {
        Self {
            port: default_port(),
            auto_start: false,
            github_token: None,
            github_repo: None,
            diary_path: default_diary_path(),
            post_to_substack: default_true(),
            post_to_twitter: false,
            post_to_linkedin: false,
            post_to_github: false,
            ghostpost_api_base_url: default_ghostpost_api_base_url(),
            daemon_token: None,
            paired_device_id: None,
            paired_user_id: None,
            paired_user_email: None,
            paired_twitter_handle: None,
            platform_preferences: default_platforms(),
            linked_accounts: HashMap::new(),
        }
    }
}

impl Config {
    /// Get the configuration directory path
    pub fn config_dir() -> Option<PathBuf> {
        ProjectDirs::from("com", "consumed", "daemon").map(|dirs| dirs.config_dir().to_path_buf())
    }

    /// Get the configuration file path
    pub fn config_path() -> Option<PathBuf> {
        Self::config_dir().map(|dir| dir.join("config.toml"))
    }

    /// Load configuration from file or create default
    pub fn load() -> Self {
        if let Some(path) = Self::config_path() {
            if path.exists() {
                if let Ok(content) = fs::read_to_string(&path) {
                    if let Ok(config) = toml::from_str(&content) {
                        return config;
                    }
                }
            }
        }
        Config::default()
    }

    /// Save configuration to file
    pub fn save(&self) -> Result<(), String> {
        let path = Self::config_path().ok_or("Could not determine config path")?;

        // Ensure directory exists
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create config dir: {}", e))?;
        }

        let content = toml::to_string_pretty(self)
            .map_err(|e| format!("Failed to serialize config: {}", e))?;

        fs::write(&path, content).map_err(|e| format!("Failed to write config: {}", e))?;

        Ok(())
    }
}

/// Thread-safe configuration state
pub struct ConfigState {
    inner: RwLock<Config>,
}

impl ConfigState {
    pub fn new() -> Self {
        Self {
            inner: RwLock::new(Config::load()),
        }
    }

    pub fn get(&self) -> Config {
        self.inner.read().unwrap().clone()
    }

    pub fn update<F>(&self, f: F) -> Result<(), String>
    where
        F: FnOnce(&mut Config),
    {
        let mut config = self.inner.write().unwrap();
        f(&mut config);
        config.save()
    }
}

impl Default for ConfigState {
    fn default() -> Self {
        Self::new()
    }
}
