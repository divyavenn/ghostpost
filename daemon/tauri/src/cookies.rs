//! Cookie conversion between Chrome extension and Playwright formats.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

/// Cookie as received from Chrome extension
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChromeCookie {
    pub name: String,
    pub value: String,
    pub domain: String,
    pub path: String,
    #[serde(default)]
    pub secure: bool,
    #[serde(default)]
    pub http_only: bool,
    #[serde(default)]
    pub same_site: Option<String>,
    #[serde(default)]
    pub expiration_date: Option<f64>,
}

/// Site-specific cookie data from extension
#[derive(Debug, Clone, Deserialize)]
pub struct SiteCookies {
    pub cookies: Vec<ChromeCookie>,
}

/// Viewport/screen dimensions
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Dimensions {
    pub width: u32,
    pub height: u32,
}

/// Full browser state from Chrome extension
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BrowserStateRequest {
    #[serde(default)]
    pub substack: Option<SiteCookies>,
    #[serde(default)]
    pub twitter: Option<SiteCookies>,
    #[serde(default)]
    pub user_agent: Option<String>,
    #[serde(default)]
    pub viewport: Option<Dimensions>,
    #[serde(default)]
    pub screen: Option<Dimensions>,
    #[serde(default)]
    pub timezone: Option<String>,
    #[serde(default)]
    pub language: Option<String>,
    #[serde(default)]
    pub languages: Option<Vec<String>>,
    #[serde(default)]
    pub platform: Option<String>,
    #[serde(default)]
    pub timestamp: Option<u64>,
}

/// Cookie in Playwright storage state format
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlaywrightCookie {
    pub name: String,
    pub value: String,
    pub domain: String,
    pub path: String,
    pub expires: f64,
    pub http_only: bool,
    pub secure: bool,
    pub same_site: String,
}

/// Common browser context for Playwright
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BrowserContext {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_agent: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub viewport: Option<Dimensions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub screen: Option<Dimensions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timezone: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,
}

impl Default for BrowserContext {
    fn default() -> Self {
        Self {
            user_agent: None,
            viewport: None,
            screen: None,
            timezone: None,
            locale: None,
        }
    }
}

/// Playwright storage state format (per-site)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageState {
    pub cookies: Vec<PlaywrightCookie>,
    #[serde(default)]
    pub origins: Vec<serde_json::Value>,
}

impl Default for StorageState {
    fn default() -> Self {
        Self {
            cookies: Vec::new(),
            origins: Vec::new(),
        }
    }
}

/// Combined browser state with all sites and common context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CombinedBrowserState {
    pub context: BrowserContext,
    pub sites: HashMap<String, StorageState>,
    #[serde(default)]
    pub updated_at: Option<u64>,
}

impl Default for CombinedBrowserState {
    fn default() -> Self {
        Self {
            context: BrowserContext::default(),
            sites: HashMap::new(),
            updated_at: None,
        }
    }
}

/// Convert Chrome sameSite value to Playwright format
fn convert_same_site(same_site: Option<&str>) -> String {
    match same_site {
        Some("no_restriction") | Some("unspecified") => "None".to_string(),
        Some("lax") => "Lax".to_string(),
        Some("strict") => "Strict".to_string(),
        Some(other) => {
            // Capitalize first letter
            let mut chars = other.chars();
            match chars.next() {
                Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
                None => "Lax".to_string(),
            }
        }
        None => "Lax".to_string(),
    }
}

/// Convert Chrome cookie to Playwright format
pub fn convert_cookie(chrome: &ChromeCookie) -> PlaywrightCookie {
    PlaywrightCookie {
        name: chrome.name.clone(),
        value: chrome.value.clone(),
        domain: chrome.domain.clone(),
        path: chrome.path.clone(),
        expires: chrome.expiration_date.unwrap_or(-1.0),
        http_only: chrome.http_only,
        secure: chrome.secure,
        same_site: convert_same_site(chrome.same_site.as_deref()),
    }
}

/// Get the browser state directory
pub fn get_state_dir() -> PathBuf {
    if let Ok(path) = std::env::var("CONSUMED_STATE_DIR") {
        PathBuf::from(path)
    } else {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".consumed")
    }
}

/// Get path for combined browser state
pub fn get_combined_state_path() -> PathBuf {
    get_state_dir().join("browser_state.json")
}

/// Get path for site-specific Playwright state (for direct use by Playwright)
pub fn get_site_state_path(site: &str) -> PathBuf {
    get_state_dir().join(format!("{}_state.json", site))
}

/// Load combined browser state
pub fn load_combined_state() -> CombinedBrowserState {
    let path = get_combined_state_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(state) = serde_json::from_str(&content) {
                return state;
            }
        }
    }
    CombinedBrowserState::default()
}

/// Save combined browser state
pub fn save_combined_state(state: &CombinedBrowserState) -> Result<(), String> {
    let dir = get_state_dir();
    fs::create_dir_all(&dir).map_err(|e| format!("Failed to create directory: {}", e))?;

    let path = get_combined_state_path();
    let content = serde_json::to_string_pretty(state)
        .map_err(|e| format!("Failed to serialize state: {}", e))?;
    fs::write(&path, content).map_err(|e| format!("Failed to write state: {}", e))?;

    // Also save individual site state files for direct Playwright use
    for (site, storage) in &state.sites {
        let site_path = get_site_state_path(site);
        let site_content = serde_json::to_string_pretty(storage)
            .map_err(|e| format!("Failed to serialize {} state: {}", site, e))?;
        fs::write(&site_path, site_content)
            .map_err(|e| format!("Failed to write {} state: {}", site, e))?;
    }

    Ok(())
}

/// Import browser state from Chrome extension
pub fn import_browser_state(request: BrowserStateRequest) -> Result<usize, String> {
    let mut state = load_combined_state();
    let mut total_cookies = 0;

    // Update browser context
    if let Some(ua) = request.user_agent {
        state.context.user_agent = Some(ua);
    }
    if let Some(vp) = request.viewport {
        state.context.viewport = Some(vp);
    }
    if let Some(sc) = request.screen {
        state.context.screen = Some(sc);
    }
    if let Some(tz) = request.timezone {
        state.context.timezone = Some(tz);
    }
    if let Some(lang) = request.language {
        state.context.locale = Some(lang);
    }

    // Import Substack cookies
    if let Some(substack) = request.substack {
        let cookies: Vec<PlaywrightCookie> = substack.cookies.iter().map(convert_cookie).collect();
        total_cookies += cookies.len();
        state.sites.insert(
            "substack".to_string(),
            StorageState {
                cookies,
                origins: Vec::new(),
            },
        );
    }

    // Import Twitter cookies
    if let Some(twitter) = request.twitter {
        let cookies: Vec<PlaywrightCookie> = twitter.cookies.iter().map(convert_cookie).collect();
        total_cookies += cookies.len();
        state.sites.insert(
            "twitter".to_string(),
            StorageState {
                cookies,
                origins: Vec::new(),
            },
        );
    }

    state.updated_at = request.timestamp;

    save_combined_state(&state)?;

    Ok(total_cookies)
}

// Keep old function for backwards compatibility
pub fn import_cookies(chrome_cookies: Vec<ChromeCookie>) -> Result<usize, String> {
    let request = BrowserStateRequest {
        substack: Some(SiteCookies {
            cookies: chrome_cookies,
        }),
        twitter: None,
        user_agent: None,
        viewport: None,
        screen: None,
        timezone: None,
        language: None,
        languages: None,
        platform: None,
        timestamp: None,
    };
    import_browser_state(request)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_convert_same_site() {
        assert_eq!(convert_same_site(Some("no_restriction")), "None");
        assert_eq!(convert_same_site(Some("lax")), "Lax");
        assert_eq!(convert_same_site(Some("strict")), "Strict");
        assert_eq!(convert_same_site(None), "Lax");
    }

    #[test]
    fn test_convert_cookie() {
        let chrome = ChromeCookie {
            name: "test".to_string(),
            value: "value".to_string(),
            domain: ".example.com".to_string(),
            path: "/".to_string(),
            secure: true,
            http_only: false,
            same_site: Some("lax".to_string()),
            expiration_date: Some(1700000000.0),
        };

        let playwright = convert_cookie(&chrome);

        assert_eq!(playwright.name, "test");
        assert_eq!(playwright.value, "value");
        assert_eq!(playwright.domain, ".example.com");
        assert_eq!(playwright.path, "/");
        assert!(playwright.secure);
        assert!(!playwright.http_only);
        assert_eq!(playwright.same_site, "Lax");
        assert_eq!(playwright.expires, 1700000000.0);
    }
}
