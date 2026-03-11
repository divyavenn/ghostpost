mod cli;

use chrono::NaiveDate;
use clap::Parser;
use cli::{Cli, Commands};
use consumed_core::{diary, error::ConsumedError, github, metadata, python};
use std::path::PathBuf;
use std::process;

fn main() {
    // Load .env file (ignore if not found)
    dotenvy::dotenv().ok();

    if let Err(e) = run() {
        eprintln!("Error: {}", e);
        process::exit(1);
    }
}

fn run() -> Result<(), ConsumedError> {
    let args = Cli::parse();

    match args.command {
        Commands::Log {
            url,
            date,
            diary_path,
            github: use_github,
        } => cmd_log(&url, date, &diary_path, use_github, args.verbose),
        Commands::Post {
            url,
            quote,
            thoughts,
            dry_run,
            no_headless,
        } => cmd_post(&url, quote, thoughts, dry_run, no_headless, args.verbose),
        Commands::Login => cmd_login(),
    }
}

/// Log a URL to the diary
fn cmd_log(
    url: &str,
    date: Option<String>,
    diary_path: &str,
    use_github: bool,
    verbose: bool,
) -> Result<(), ConsumedError> {
    if verbose {
        eprintln!("URL: {}", url);
        eprintln!("Date: {:?}", date);
        if use_github {
            eprintln!("Mode: GitHub");
        } else {
            eprintln!("Diary path: {}", diary_path);
        }
    }

    // Parse date or use today
    let entry_date = match date {
        Some(ref date_str) => NaiveDate::parse_from_str(date_str, "%Y-%m-%d")
            .map_err(|e| ConsumedError::InvalidDate(format!("{}: {}", date_str, e)))?,
        None => chrono::Local::now().date_naive(),
    };

    if verbose {
        eprintln!("Extracting metadata from URL...");
    }

    // Extract metadata
    let entry = metadata::extract(url)?;

    if verbose {
        eprintln!("Title: {}", entry.title);
        eprintln!("Author: {:?}", entry.author);
    }

    if use_github {
        // Commit to GitHub
        let token = std::env::var("GITHUB_TOKEN")
            .map_err(|_| ConsumedError::GitHub("GITHUB_TOKEN env var not set".to_string()))?;
        let repo = std::env::var("GITHUB_REPO")
            .map_err(|_| ConsumedError::GitHub("GITHUB_REPO env var not set".to_string()))?;
        let file_path = std::env::var("LOG_FILE").unwrap_or_else(|_| "reading_now.md".to_string());

        github::add_entry_to_github(url, &repo, &file_path, &token)?;
    } else {
        // Local file
        let path = PathBuf::from(diary_path);
        let mut diary_data = diary::load_diary(&path)?;

        if verbose {
            eprintln!("Loaded diary with {} dates", diary_data.dates.len());
        }

        diary::insert_entry(&mut diary_data, entry_date, entry.clone());

        if verbose {
            eprintln!("Inserted entry, now {} dates", diary_data.dates.len());
        }

        diary::save_diary(&diary_data, &path)?;
    }

    // Print success message
    if let Some(ref author) = entry.author {
        println!("Added: [{}]({}), by {}", entry.title, entry.url, author);
    } else {
        println!("Added: [{}]({})", entry.title, entry.url);
    }

    Ok(())
}

/// Log URL and post to Substack Notes
fn cmd_post(
    url: &str,
    quote: Option<String>,
    thoughts: Option<String>,
    dry_run: bool,
    no_headless: bool,
    verbose: bool,
) -> Result<(), ConsumedError> {
    if verbose {
        eprintln!("URL: {}", url);
        eprintln!("Quote: {:?}", quote);
        eprintln!("Thoughts: {:?}", thoughts);
        eprintln!("Dry run: {}", dry_run);
    }

    // Step 1: Extract metadata
    if verbose {
        eprintln!("Extracting metadata...");
    }
    let entry = metadata::extract(url)?;

    if verbose {
        eprintln!("Title: {}", entry.title);
        eprintln!("Author: {:?}", entry.author);
    }

    // Step 2: Log to GitHub (if configured)
    if std::env::var("GITHUB_TOKEN").is_ok() && std::env::var("GITHUB_REPO").is_ok() {
        let token = std::env::var("GITHUB_TOKEN").unwrap();
        let repo = std::env::var("GITHUB_REPO").unwrap();
        let file_path = std::env::var("LOG_FILE").unwrap_or_else(|_| "reading_now.md".to_string());

        if verbose {
            eprintln!("Logging to GitHub...");
        }
        github::add_entry_to_github(url, &repo, &file_path, &token)?;
        println!("Logged to GitHub: {}", entry.title);
    }

    // Step 3: Post to Substack via Python
    if verbose {
        eprintln!("Spawning Python for Substack posting...");
    }

    python::post_to_substack(
        &entry,
        quote.as_deref(),
        thoughts.as_deref(),
        !no_headless,
        dry_run,
    )?;

    Ok(())
}

/// Login to Substack (one-time setup)
fn cmd_login() -> Result<(), ConsumedError> {
    python::substack_login()
}
