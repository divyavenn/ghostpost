pub mod article;
pub mod arxiv;
pub mod extractor;
pub mod github;
pub mod goodreads;
pub mod header;
pub mod imdb;
pub mod letterboxd;
pub mod substack;
pub mod wikipedia;
pub mod youtube;

use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use crate::python::extract_with_llm;
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use std::env;
use std::time::Duration;
use url::Url;

use article::ArticleExtractor;
use arxiv::ArXivExtractor;
use extractor::MetadataExtractor;
use github::GitHubExtractor;
use goodreads::GoodreadsExtractor;
use imdb::ImdbExtractor;
use letterboxd::LetterboxdExtractor;
use substack::SubstackExtractor;
use wikipedia::WikipediaExtractor;
use youtube::YouTubeExtractor;

/// Detect content type from URL patterns alone (no HTTP request).
pub fn detect_content_type(url_str: &str) -> ContentType {
    let url = match Url::parse(url_str) {
        Ok(u) => u,
        Err(_) => return ContentType::Unknown,
    };

    let host = match url.host_str() {
        Some(h) => h,
        None => return ContentType::Unknown,
    };

    // YouTube
    if matches!(
        host,
        "youtube.com" | "www.youtube.com" | "m.youtube.com" | "youtu.be"
    ) {
        return ContentType::YouTube;
    }

    // ArXiv
    if host == "arxiv.org" {
        return ContentType::ResearchPaper;
    }

    // GitHub
    if host == "github.com" {
        return ContentType::GitHub;
    }

    // Substack
    if host.ends_with(".substack.com") {
        return ContentType::Substack;
    }

    // Goodreads
    if host == "goodreads.com" || host == "www.goodreads.com" {
        return ContentType::Book;
    }

    // IMDB
    if host == "imdb.com" || host == "www.imdb.com" || host == "m.imdb.com" {
        return ContentType::Movie;
    }

    // Letterboxd
    if host == "letterboxd.com" || host == "www.letterboxd.com" {
        return ContentType::Movie;
    }

    // Wikipedia
    if host == "wikipedia.org" || host.ends_with(".wikipedia.org") {
        return ContentType::Article;
    }

    // Twitter/X
    if host == "x.com" || host == "www.x.com" || host == "twitter.com" || host == "www.twitter.com"
    {
        return ContentType::Tweet;
    }

    // Medium
    if host == "medium.com" || host.ends_with(".medium.com") {
        return ContentType::Medium;
    }

    // PDF (path-based)
    if url.path().to_lowercase().ends_with(".pdf") {
        return ContentType::PDF;
    }

    // Default fallback
    ContentType::Article
}

/// Extract og:image or twitter:image from HTML
fn extract_image_url(html: &str) -> Option<String> {
    let document = Html::parse_document(html);

    // Try og:image
    if let Ok(sel) = Selector::parse("meta[property='og:image']") {
        if let Some(el) = document.select(&sel).next() {
            if let Some(url) = el.value().attr("content") {
                let url = url.trim();
                if !url.is_empty() {
                    return Some(url.to_string());
                }
            }
        }
    }

    // Fallback: twitter:image
    if let Ok(sel) = Selector::parse("meta[name='twitter:image']") {
        if let Some(el) = document.select(&sel).next() {
            if let Some(url) = el.value().attr("content") {
                let url = url.trim();
                if !url.is_empty() {
                    return Some(url.to_string());
                }
            }
        }
    }

    None
}

/// Extract metadata from a URL using the appropriate extractor
pub fn extract(url_str: &str) -> Result<Entry> {
    let url = Url::parse(url_str).map_err(|e| ConsumedError::InvalidUrl(format!("{}", e)))?;

    if !matches!(url.scheme(), "http" | "https") {
        return Err(ConsumedError::InvalidUrl(format!(
            "URL must use HTTP or HTTPS scheme, got: {}",
            url.scheme()
        )));
    }

    let client = Client::builder()
        .timeout(Duration::from_secs(30)) // Longer timeout for slow sites like IMDB
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .build()
        .map_err(|e| ConsumedError::Network(e))?;

    // Extractors in priority order (most specific first)
    let extractors: Vec<Box<dyn MetadataExtractor>> = vec![
        Box::new(YouTubeExtractor::new()),
        Box::new(ArXivExtractor::new()),
        Box::new(GitHubExtractor::new()),
        Box::new(SubstackExtractor::new()),
        Box::new(GoodreadsExtractor::new()),
        Box::new(ImdbExtractor::new()),
        Box::new(LetterboxdExtractor::new()),
        Box::new(WikipediaExtractor::new()),
        Box::new(ArticleExtractor::new()), // Fallback - handles everything else
    ];

    let mut best_entry: Option<Entry> = None;

    for extractor in extractors.iter() {
        if extractor.can_handle(&url) {
            match extractor.extract(&url, &client) {
                Ok(entry) => {
                    best_entry = Some(entry);
                    break;
                }
                Err(e) => {
                    eprintln!("Warning: Extractor failed: {}", e);
                }
            }
        }
    }

    let source = url.host_str().unwrap_or("unknown").to_string();

    // Check if we should try LLM extraction as fallback
    let should_try_llm = match &best_entry {
        Some(entry) => {
            // Try LLM if title is just the source (fallback title) or content type is unknown
            entry.title == source || entry.content_type == ContentType::Unknown
        }
        None => true,
    };

    // Try LLM extraction if API key is available and extraction was poor
    if should_try_llm && env::var("ANTHROPIC_API_KEY").is_ok() {
        eprintln!("Trying LLM extraction for better metadata...");

        // Fetch HTML for LLM extraction
        if let Ok(response) = client
            .get(url.as_str())
            .header(
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            .send()
        {
            if let Ok(html) = response.text() {
                match extract_with_llm(&html, url_str) {
                    Ok(llm_entry) => {
                        eprintln!("LLM extraction successful: {}", llm_entry.title);
                        return Ok(llm_entry);
                    }
                    Err(e) => {
                        eprintln!("LLM extraction failed: {}", e);
                    }
                }
            }
        }
    }

    let mut entry = best_entry.unwrap_or_else(|| {
        Entry::new(
            source.clone(),
            url.to_string(),
            source,
            ContentType::Unknown,
        )
    });

    // Extract og:image for books and movies (posters/covers)
    if entry.image_url.is_none()
        && matches!(
            entry.content_type,
            ContentType::Book | ContentType::Movie | ContentType::TVShow
        )
    {
        if let Ok(response) = client.get(url.as_str()).send() {
            if let Ok(html) = response.text() {
                entry.image_url = extract_image_url(&html);
            }
        }
    }

    Ok(entry)
}
