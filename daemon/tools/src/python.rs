//! Spawn Python subprocesses for browser automation and LLM extraction.

use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

/// Get the path to the Python scripts directory
fn get_python_dir() -> PathBuf {
    // Check CONSUMED_PYTHON_DIR env var first
    if let Ok(dir) = env::var("CONSUMED_PYTHON_DIR") {
        return PathBuf::from(dir);
    }

    // Default: python/ directory relative to executable or current dir
    let exe_dir = env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()));

    if let Some(dir) = exe_dir {
        let python_dir = dir.join("python");
        if python_dir.exists() {
            return python_dir;
        }
    }

    let project_dir = PathBuf::from("tools/python");
    if project_dir.exists() {
        return project_dir;
    }

    // Fallback to current directory
    PathBuf::from("python")
}

fn run_python_file(script_path: PathBuf, args: &[&str]) -> Result<String> {
    let python_dir = get_python_dir();

    let output = Command::new("uv")
        .arg("run")
        .arg("--project")
        .arg(&python_dir)
        .arg("python")
        .arg(&script_path)
        .args(args)
        .output()
        .map_err(|e| ConsumedError::Python(format!("Failed to spawn Python: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(ConsumedError::Python(format!(
            "Python script failed: {}",
            stderr
        )));
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

/// Login to Substack (interactive, opens browser)
pub fn substack_login() -> Result<()> {
    let script = get_python_dir().join("tasks").join("browser.py");

    println!("Opening browser for Substack login...");
    run_python_file(script, &[])?;
    println!("Login complete. Browser state saved.");
    Ok(())
}

/// Post to Substack Notes
pub fn post_to_substack(
    entry: &Entry,
    quote: Option<&str>,
    thoughts: Option<&str>,
    headless: bool,
    dry_run: bool,
) -> Result<()> {
    let mut parts = vec![entry.title.clone()];
    if let Some(a) = &entry.author {
        parts.push(format!("by {}", a));
    }
    if let Some(q) = quote {
        parts.push(format!("\"{}\"", q));
    }
    if let Some(t) = thoughts {
        parts.push(t.to_string());
    }
    if !entry.url.is_empty() {
        parts.push(entry.url.clone());
    }
    let content = parts.join("\n\n");

    if dry_run {
        println!("DRY RUN - Would post:\n{}\n", content);
        return Ok(());
    }

    let _ = headless;
    let script = get_python_dir().join("tasks").join("substack_notes.py");
    let output = run_python_file(script, &[&content])?;
    print!("{output}");
    Ok(())
}

/// Extract metadata from HTML using LLM
pub fn extract_with_llm(html: &str, url: &str) -> Result<Entry> {
    // Write HTML to a temp file
    let temp_dir = std::env::temp_dir();
    let html_file = temp_dir.join(format!("consumed_llm_{}.html", std::process::id()));

    fs::write(&html_file, html)
        .map_err(|e| ConsumedError::Python(format!("Failed to write temp HTML file: {}", e)))?;

    let script = get_python_dir().join("tasks").join("llm_extract.py");
    let result = run_python_file(script, &[url, html_file.to_str().unwrap_or("")]);

    // Clean up temp file
    let _ = fs::remove_file(&html_file);

    let output = result?;

    // Parse JSON response
    let parsed: serde_json::Value = serde_json::from_str(&output)
        .map_err(|e| ConsumedError::Python(format!("Failed to parse LLM response: {}", e)))?;

    if let Some(error) = parsed.get("error").and_then(|e| e.as_str()) {
        return Err(ConsumedError::Python(format!(
            "LLM extraction failed: {}",
            error
        )));
    }

    let title = parsed
        .get("title")
        .and_then(|t| t.as_str())
        .unwrap_or("Unknown")
        .to_string();

    let author = parsed
        .get("author")
        .and_then(|a| a.as_str())
        .map(|s| s.to_string());

    let content_type_str = parsed
        .get("content_type")
        .and_then(|c| c.as_str())
        .unwrap_or("unknown");

    let content_type = match content_type_str {
        "article" => ContentType::Article,
        "book" => ContentType::Book,
        "movie" => ContentType::Movie,
        "tv_show" => ContentType::TVShow,
        "podcast" => ContentType::Podcast,
        "youtube" => ContentType::YouTube,
        "research_paper" => ContentType::ResearchPaper,
        "pdf" => ContentType::PDF,
        "github" => ContentType::GitHub,
        "substack" => ContentType::Substack,
        "medium" => ContentType::Medium,
        "tweet" => ContentType::Tweet,
        _ => ContentType::Unknown,
    };

    // Extract source from URL
    let source = url::Url::parse(url)
        .ok()
        .and_then(|u| u.host_str().map(|h| h.to_string()))
        .unwrap_or_else(|| "unknown".to_string());

    let mut entry = Entry::new(title, url.to_string(), source, content_type);
    if let Some(a) = author {
        entry = entry.with_author(a);
    }

    Ok(entry)
}
