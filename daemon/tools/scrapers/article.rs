use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use regex::Regex;
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct ArticleExtractor;

impl ArticleExtractor {
    pub fn new() -> Self {
        Self
    }

    /// Determine content type from URL
    fn detect_content_type(&self, url: &Url) -> ContentType {
        let host = url.host_str().unwrap_or("");
        let path = url.path().to_lowercase();

        if host == "medium.com" || host.ends_with(".medium.com") {
            return ContentType::Medium;
        }

        if path.ends_with(".pdf") {
            return ContentType::PDF;
        }

        ContentType::Article
    }

    /// Clean up title by removing site name suffixes
    fn clean_title(&self, title: &str, url: &Url) -> String {
        let title = title.trim();

        // Common separators used to append site names
        let separators = [" | ", " - ", " — ", " · ", " :: ", " // ", " « ", " » "];

        // Get domain for comparison (normalize: remove www, get first part)
        let domain = url.host_str().unwrap_or("");
        let domain_clean = domain.strip_prefix("www.").unwrap_or(domain);
        let domain_parts: Vec<&str> = domain_clean.split('.').collect();
        let site_name = domain_parts.first().unwrap_or(&"").to_lowercase();
        // Also create a version without common separators for matching "danwang" to "Dan Wang"
        let site_name_no_spaces: String =
            site_name.chars().filter(|c| c.is_alphanumeric()).collect();

        for sep in separators {
            if let Some(idx) = title.rfind(sep) {
                let suffix = &title[idx + sep.len()..];
                let suffix_lower = suffix.to_lowercase();
                let suffix_no_spaces: String = suffix_lower
                    .chars()
                    .filter(|c| c.is_alphanumeric())
                    .collect();

                // Check if suffix looks like a site name or author name matching domain
                if suffix.len() < 40
                    && (suffix_lower.contains(&site_name)
                        || site_name_no_spaces.contains(&suffix_no_spaces)
                        || suffix_no_spaces.contains(&site_name_no_spaces)
                        || suffix_lower.contains("blog")
                        || suffix_lower.contains("home")
                        || suffix_lower.contains("newsletter"))
                {
                    return title[..idx].trim().to_string();
                }
            }
        }

        title.to_string()
    }

    /// Try to extract author from various sources in the HTML
    fn extract_author(&self, document: &Html, html: &str) -> Option<String> {
        // 1. Try JSON-LD structured data
        if let Some(author) = self.extract_from_json_ld(html) {
            return Some(author);
        }

        // 2. Try standard meta tags
        let meta_selectors = [
            "meta[name='author']",
            "meta[property='author']",
            "meta[property='article:author']",
            "meta[property='og:article:author']",
            "meta[name='dc.creator']",
            "meta[name='citation_author']",
        ];

        for selector_str in meta_selectors {
            if let Ok(selector) = Selector::parse(selector_str) {
                if let Some(el) = document.select(&selector).next() {
                    if let Some(content) = el.value().attr("content") {
                        let author = content.trim();
                        if !author.is_empty() && self.is_valid_author(author) {
                            return Some(author.to_string());
                        }
                    }
                }
            }
        }

        // 3. Try common author element patterns
        let author_selectors = [
            ".author",
            ".byline",
            ".post-author",
            ".entry-author",
            ".author-name",
            ".article-author",
            "[rel='author']",
            "[itemprop='author']",
            ".writer",
            ".contributor",
            "a[href*='/author/']",
            "a[href*='/writers/']",
            ".by-author",
            ".meta-author",
        ];

        for selector_str in author_selectors {
            if let Ok(selector) = Selector::parse(selector_str) {
                if let Some(el) = document.select(&selector).next() {
                    let text = el.text().collect::<String>();
                    let author = self.clean_author_text(&text);
                    if !author.is_empty() && self.is_valid_author(&author) {
                        return Some(author);
                    }
                }
            }
        }

        // 4. Try to find "by [Author]" pattern in the page
        if let Some(author) = self.extract_from_byline_pattern(html) {
            return Some(author);
        }

        None
    }

    /// Extract author from JSON-LD structured data
    fn extract_from_json_ld(&self, html: &str) -> Option<String> {
        let re = Regex::new(r#"<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>"#)
            .ok()?;

        for cap in re.captures_iter(html) {
            if let Some(json_str) = cap.get(1) {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(json_str.as_str()) {
                    // Handle single object or array
                    let items = if json.is_array() {
                        json.as_array().unwrap().clone()
                    } else {
                        vec![json]
                    };

                    for item in items {
                        // Check for author field
                        if let Some(author) = item.get("author") {
                            if let Some(name) = author.get("name").and_then(|n| n.as_str()) {
                                return Some(name.to_string());
                            }
                            if let Some(name) = author.as_str() {
                                return Some(name.to_string());
                            }
                            // Handle array of authors
                            if let Some(authors) = author.as_array() {
                                let names: Vec<String> = authors
                                    .iter()
                                    .filter_map(|a| {
                                        a.get("name")
                                            .and_then(|n| n.as_str())
                                            .map(|s| s.to_string())
                                            .or_else(|| a.as_str().map(|s| s.to_string()))
                                    })
                                    .collect();
                                if !names.is_empty() {
                                    return Some(names.join(", "));
                                }
                            }
                        }

                        // Check for creator field (used by some sites)
                        if let Some(creator) = item.get("creator") {
                            if let Some(name) = creator.as_str() {
                                return Some(name.to_string());
                            }
                        }
                    }
                }
            }
        }

        None
    }

    /// Extract author from "by [Author]" patterns in text
    fn extract_from_byline_pattern(&self, html: &str) -> Option<String> {
        // Look for common byline patterns
        let patterns = [
            r"(?i)\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
            r"(?i)\bwritten\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
            r"(?i)\bauthor:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b",
        ];

        for pattern in patterns {
            if let Ok(re) = Regex::new(pattern) {
                if let Some(cap) = re.captures(html) {
                    if let Some(author) = cap.get(1) {
                        let name = author.as_str().trim();
                        if self.is_valid_author(name) {
                            return Some(name.to_string());
                        }
                    }
                }
            }
        }

        None
    }

    /// Clean author text by removing common prefixes
    fn clean_author_text(&self, text: &str) -> String {
        let text = text.trim();

        // Remove common prefixes
        let prefixes = [
            "by ",
            "By ",
            "BY ",
            "written by ",
            "Written by ",
            "Author: ",
            "author: ",
        ];
        let mut result = text;
        for prefix in prefixes {
            if let Some(stripped) = result.strip_prefix(prefix) {
                result = stripped;
            }
        }

        result.trim().to_string()
    }

    /// Check if extracted text looks like a valid author name
    fn is_valid_author(&self, text: &str) -> bool {
        let text = text.trim();

        // Too short or too long
        if text.len() < 2 || text.len() > 100 {
            return false;
        }

        // Should not contain newlines
        if text.contains('\n') || text.contains('\r') {
            return false;
        }

        // Likely not an author name
        let invalid_patterns = [
            "http",
            "www.",
            ".com",
            ".org",
            "@",
            "#",
            "click",
            "subscribe",
            "read more",
            "share",
            "comment",
            "reply",
            "admin",
            "administrator",
        ];

        let lower = text.to_lowercase();
        for pattern in invalid_patterns {
            if lower.contains(pattern) {
                return false;
            }
        }

        // Common verbs/words that appear after "by" but aren't names
        let invalid_starts = [
            "sucking", "reading", "working", "going", "doing", "making", "using", "looking",
            "getting", "being", "having", "taking", "coming", "seeing", "knowing", "thinking",
            "giving", "putting", "telling", "asking", "trying", "the", "a", "an", "this", "that",
            "our", "your", "their", "its", "my", "his", "her",
        ];

        let first_word = lower.split_whitespace().next().unwrap_or("");
        for word in invalid_starts {
            if first_word == word {
                return false;
            }
        }

        // Should have 2-4 words (typical name format)
        let word_count = text.split_whitespace().count();
        if word_count > 5 {
            return false;
        }

        // Should contain at least one letter
        text.chars().any(|c| c.is_alphabetic())
    }

    fn try_webpage(&self, url: &Url, _client: &Client) -> Option<Entry> {
        match webpage::Webpage::from_url(url.as_str(), webpage::WebpageOptions::default()) {
            Ok(page) => {
                let title = page.html.title.clone()?;
                let clean_title = self.clean_title(&title, url);

                let author = page
                    .html
                    .opengraph
                    .properties
                    .get("article:author")
                    .or_else(|| page.html.opengraph.properties.get("author"))
                    .cloned();

                let source = url.host_str().unwrap_or("unknown").to_string();
                let content_type = self.detect_content_type(url);

                let mut entry = Entry::new(clean_title, url.to_string(), source, content_type);
                if let Some(a) = author {
                    if self.is_valid_author(&a) {
                        entry = entry.with_author(a);
                    }
                }
                Some(entry)
            }
            Err(_) => None,
        }
    }

    fn try_full_extraction(&self, html: &str, url: &Url) -> Option<Entry> {
        let document = Html::parse_document(html);

        // Extract title
        let title = self.extract_title(&document, url)?;

        // Extract author with enhanced methods
        let author = self.extract_author(&document, html);

        let source = url.host_str().unwrap_or("unknown").to_string();
        let content_type = self.detect_content_type(url);

        let mut entry = Entry::new(title, url.to_string(), source, content_type);
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Some(entry)
    }

    fn extract_title(&self, document: &Html, url: &Url) -> Option<String> {
        // Try og:title first
        if let Ok(selector) = Selector::parse("meta[property='og:title']") {
            if let Some(el) = document.select(&selector).next() {
                if let Some(content) = el.value().attr("content") {
                    return Some(self.clean_title(content, url));
                }
            }
        }

        // Try <title> tag
        if let Ok(selector) = Selector::parse("title") {
            if let Some(el) = document.select(&selector).next() {
                let title = el.text().collect::<String>();
                return Some(self.clean_title(&title, url));
            }
        }

        // Try h1
        if let Ok(selector) = Selector::parse("h1") {
            if let Some(el) = document.select(&selector).next() {
                let title = el.text().collect::<String>();
                if !title.trim().is_empty() {
                    return Some(title.trim().to_string());
                }
            }
        }

        None
    }

    fn create_fallback(&self, url: &Url) -> Entry {
        let source = url.host_str().unwrap_or("unknown").to_string();
        Entry::new(
            source.clone(),
            url.to_string(),
            source,
            ContentType::Unknown,
        )
    }
}

impl MetadataExtractor for ArticleExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        matches!(url.scheme(), "http" | "https")
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        // Fetch HTML first for full extraction
        let html = client
            .get(url.as_str())
            .header(
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        // Try full extraction with enhanced author detection
        if let Some(entry) = self.try_full_extraction(&html, url) {
            return Ok(entry);
        }

        // Try webpage crate as fallback
        if let Some(entry) = self.try_webpage(url, client) {
            return Ok(entry);
        }

        Ok(self.create_fallback(url))
    }
}
