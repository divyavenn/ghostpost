//! Browser detection and CDP (Chrome DevTools Protocol) management.
//!
//! Detects the user's default Chromium-based browser on macOS, and ensures
//! it is running with `--remote-debugging-port=9222` so Playwright can
//! connect to the live session.

use std::net::TcpStream;
use std::process::Command;
use std::time::Duration;

const CDP_PORT: u16 = 9222;
const CDP_ADDR: &str = "127.0.0.1:9222";

/// Info about a known Chromium-based browser.
struct BrowserInfo {
    /// The macOS application name (e.g. "Google Chrome").
    app_name: &'static str,
}

/// Map a macOS bundle identifier to a known Chromium browser.
fn browser_from_bundle_id(bundle_id: &str) -> Option<BrowserInfo> {
    let app_name = match bundle_id {
        "com.google.chrome" => "Google Chrome",
        "com.brave.browser" => "Brave Browser",
        "com.microsoft.edgemac" => "Microsoft Edge",
        "company.thebrowser.browser" => "Arc",
        "com.vivaldi.vivaldi" => "Vivaldi",
        "org.chromium.chromium" => "Chromium",
        _ => return None,
    };
    Some(BrowserInfo { app_name })
}

/// Detect the user's default browser from macOS LaunchServices preferences.
///
/// Reads `com.apple.LaunchServices/com.apple.launchservices.secure.plist`
/// via `plutil`, finds the handler for the `https` URL scheme, and maps
/// the bundle ID to a known Chromium browser.
#[cfg(target_os = "macos")]
fn detect_default_browser() -> Option<BrowserInfo> {
    let home = std::env::var("HOME").ok()?;
    let plist_path = format!(
        "{}/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist",
        home
    );

    let output = Command::new("plutil")
        .args(["-convert", "json", "-o", "-", &plist_path])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let json: serde_json::Value = serde_json::from_slice(&output.stdout).ok()?;

    // The plist contains an array of handler entries under "LSHandlers".
    // We look for the one with LSHandlerURLScheme == "https".
    let handlers = json.get("LSHandlers")?.as_array()?;
    for handler in handlers {
        let scheme = handler
            .get("LSHandlerURLScheme")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if scheme.eq_ignore_ascii_case("https") {
            let bundle_id = handler
                .get("LSHandlerRoleAll")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            return browser_from_bundle_id(&bundle_id.to_lowercase());
        }
    }

    None
}

/// Check whether CDP is already listening on port 9222.
#[cfg(target_os = "macos")]
fn is_cdp_active() -> bool {
    TcpStream::connect_timeout(&CDP_ADDR.parse().unwrap(), Duration::from_millis(500)).is_ok()
}

/// Check whether the given browser application is currently running.
#[cfg(target_os = "macos")]
fn is_browser_running(browser: &BrowserInfo) -> bool {
    Command::new("pgrep")
        .args(["-x", browser.app_name])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

/// Gracefully quit the browser via AppleScript, then poll until it exits.
#[cfg(target_os = "macos")]
fn quit_browser(browser: &BrowserInfo) {
    let script = format!(r#"tell application "{}" to quit"#, browser.app_name);
    let _ = Command::new("osascript").args(["-e", &script]).status();

    // Poll for up to 10 seconds for the browser to fully exit.
    for _ in 0..20 {
        std::thread::sleep(Duration::from_millis(500));
        if !is_browser_running(browser) {
            return;
        }
    }
    eprintln!(
        "[browser] warning: {} did not exit within 10 s",
        browser.app_name
    );
}

/// Launch the browser with `--remote-debugging-port=9222` and wait for CDP.
#[cfg(target_os = "macos")]
fn launch_browser_with_cdp(browser: &BrowserInfo) -> Result<(), String> {
    let _ = Command::new("open")
        .args([
            "-a",
            browser.app_name,
            "--args",
            &format!("--remote-debugging-port={}", CDP_PORT),
        ])
        .status();

    // Wait up to 15 seconds for CDP to become available.
    for _ in 0..30 {
        std::thread::sleep(Duration::from_millis(500));
        if is_cdp_active() {
            return Ok(());
        }
    }
    Err(format!(
        "{} launched but CDP did not become active within 15 s",
        browser.app_name
    ))
}

/// Ensure a Chromium browser is running with CDP on port 9222.
///
/// Returns `Ok(message)` describing what happened, or `Err` on failure.
#[cfg(target_os = "macos")]
pub fn ensure_cdp() -> Result<String, String> {
    // Already active — nothing to do.
    if is_cdp_active() {
        return Ok("CDP already active on port 9222".into());
    }

    let browser = match detect_default_browser() {
        Some(b) => b,
        None => return Ok("Default browser is not Chromium-based; skipping CDP setup".into()),
    };

    if is_browser_running(&browser) {
        // Browser is running but without CDP — restart it.
        eprintln!(
            "[browser] {} is running without CDP, restarting…",
            browser.app_name
        );
        quit_browser(&browser);
    }

    launch_browser_with_cdp(&browser)?;
    Ok(format!(
        "Launched {} with CDP on port {}",
        browser.app_name, CDP_PORT
    ))
}
