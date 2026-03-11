use crate::diary;
use crate::error::{ConsumedError, Result};
use crate::metadata;
use crate::models::Entry;
use chrono::Local;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct GitHubFileResponse {
    content: String,
    sha: String,
}

/// Add a URL to the diary stored on GitHub
///
/// # Arguments
/// * `url` - The URL to add
/// * `repo` - GitHub repo in "owner/repo" format
/// * `file_path` - Path to diary file in repo (e.g., "diary.md")
/// * `token` - GitHub personal access token
///
/// # Example
/// ```ignore
/// consumed_core::github::add_entry_to_github(
///     "https://example.com/article",
///     "myuser/reading-log",
///     "diary.md",
///     "ghp_xxxxxxxxxxxx"
/// )?;
/// ```
pub fn add_entry_to_github(url: &str, repo: &str, file_path: &str, token: &str) -> Result<Entry> {
    add_entry_to_github_with_date(url, repo, file_path, token, None)
}

/// Add a URL to the diary stored on GitHub with an optional specific date
pub fn add_entry_to_github_with_date(
    url: &str,
    repo: &str,
    file_path: &str,
    token: &str,
    date: Option<chrono::NaiveDate>,
) -> Result<Entry> {
    // 1. Extract metadata from URL
    let entry = metadata::extract(url)?;

    // 2. Get current diary from GitHub
    let (diary_content, sha) = fetch_diary_from_github(repo, file_path, token)?;

    // 3. Parse diary and insert entry
    let mut diary = diary::parse_diary(&diary_content);
    let entry_date = date.unwrap_or_else(|| Local::now().date_naive());
    diary::insert_entry(&mut diary, entry_date, entry.clone());

    // 4. Serialize and commit back
    let updated_content = diary::serialize_diary(&diary);
    commit_diary_to_github(repo, file_path, token, &sha, &updated_content, &entry.title)?;

    Ok(entry)
}

/// Fetch diary file from GitHub
fn fetch_diary_from_github(repo: &str, file_path: &str, token: &str) -> Result<(String, String)> {
    let client = reqwest::blocking::Client::new();
    let api_url = format!(
        "https://api.github.com/repos/{}/contents/{}",
        repo, file_path
    );

    let response = client
        .get(&api_url)
        .header("Authorization", format!("token {}", token))
        .header("User-Agent", "consumed/0.1.0")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .map_err(|e| ConsumedError::Network(e))?;

    if response.status() == 404 {
        // File doesn't exist yet, return empty diary
        return Ok((String::new(), String::new()));
    }

    if !response.status().is_success() {
        return Err(ConsumedError::GitHub(format!(
            "Failed to fetch diary: HTTP {}",
            response.status()
        )));
    }

    let file_response: GitHubFileResponse = response
        .json()
        .map_err(|e| ConsumedError::GitHub(format!("Failed to parse response: {}", e)))?;

    // Decode base64 content
    let content = base64_decode(&file_response.content)?;

    Ok((content, file_response.sha))
}

/// Commit updated diary to GitHub
fn commit_diary_to_github(
    repo: &str,
    file_path: &str,
    token: &str,
    sha: &str,
    content: &str,
    title: &str,
) -> Result<()> {
    let client = reqwest::blocking::Client::new();
    let api_url = format!(
        "https://api.github.com/repos/{}/contents/{}",
        repo, file_path
    );

    // Truncate title for commit message
    let short_title: String = title.chars().take(50).collect();
    let message = format!("Add: {}", short_title);

    // If sha is empty, this is a new file (don't include sha)
    let body = if sha.is_empty() {
        serde_json::json!({
            "message": message,
            "content": base64_encode(content),
        })
    } else {
        serde_json::json!({
            "message": message,
            "content": base64_encode(content),
            "sha": sha,
        })
    };

    let response = client
        .put(&api_url)
        .header("Authorization", format!("token {}", token))
        .header("User-Agent", "consumed/0.1.0")
        .header("Accept", "application/vnd.github.v3+json")
        .json(&body)
        .send()
        .map_err(|e| ConsumedError::Network(e))?;

    if !response.status().is_success() {
        let status = response.status();
        let error_body = response.text().unwrap_or_default();
        return Err(ConsumedError::GitHub(format!(
            "Failed to commit: HTTP {} - {}",
            status, error_body
        )));
    }

    Ok(())
}

fn base64_decode(encoded: &str) -> Result<String> {
    // GitHub returns base64 with newlines, remove them
    let cleaned: String = encoded.chars().filter(|c| !c.is_whitespace()).collect();

    use base64::{engine::general_purpose::STANDARD, Engine};
    let bytes = STANDARD
        .decode(&cleaned)
        .map_err(|e| ConsumedError::GitHub(format!("Base64 decode error: {}", e)))?;

    String::from_utf8(bytes)
        .map_err(|e| ConsumedError::GitHub(format!("UTF-8 decode error: {}", e)))
}

fn base64_encode(content: &str) -> String {
    use base64::{engine::general_purpose::STANDARD, Engine};
    STANDARD.encode(content.as_bytes())
}
