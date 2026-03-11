use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct GoodreadsExtractor;

impl GoodreadsExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_from_page(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .header(
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch Goodreads page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

        // Try og:title first, then fall back to other selectors
        let title = Selector::parse("meta[property='og:title']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
                    .map(|s| s.to_string())
            })
            .or_else(|| {
                // Try the book title heading
                Selector::parse("h1.Text__title1")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .map(|el| el.text().collect::<String>().trim().to_string())
                    })
            })
            .or_else(|| {
                // Legacy selector
                Selector::parse("#bookTitle").ok().and_then(|selector| {
                    document
                        .select(&selector)
                        .next()
                        .map(|el| el.text().collect::<String>().trim().to_string())
                })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find book title".to_string(),
            })?;

        // Try to extract author
        let author = Selector::parse("meta[property='books:author']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
                    .map(|s| s.to_string())
            })
            .or_else(|| {
                // Try author link
                Selector::parse("a.ContributorLink")
                    .ok()
                    .and_then(|selector| {
                        let authors: Vec<String> = document
                            .select(&selector)
                            .map(|el| el.text().collect::<String>().trim().to_string())
                            .filter(|s| !s.is_empty())
                            .collect();
                        if authors.is_empty() {
                            None
                        } else {
                            Some(authors.join(", "))
                        }
                    })
            })
            .or_else(|| {
                // Legacy selector
                Selector::parse("#bookAuthors a.authorName")
                    .ok()
                    .and_then(|selector| {
                        let authors: Vec<String> = document
                            .select(&selector)
                            .map(|el| el.text().collect::<String>().trim().to_string())
                            .collect();
                        if authors.is_empty() {
                            None
                        } else {
                            Some(authors.join(", "))
                        }
                    })
            });

        let mut entry = Entry::new(
            title,
            url.to_string(),
            "goodreads.com".to_string(),
            ContentType::Book,
        );
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for GoodreadsExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str()
            .map(|host| host == "goodreads.com" || host == "www.goodreads.com")
            .unwrap_or(false)
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
