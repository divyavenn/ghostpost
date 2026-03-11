use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct WikipediaExtractor;

impl WikipediaExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_from_page(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .header("User-Agent", "consumed/0.1.0")
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch Wikipedia page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

        // Extract title from og:title or the h1
        let title = Selector::parse("meta[property='og:title']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
                    .map(|s| {
                        // Remove " - Wikipedia" suffix if present
                        s.trim_end_matches(" - Wikipedia").to_string()
                    })
            })
            .or_else(|| {
                Selector::parse("h1#firstHeading")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .map(|el| el.text().collect::<String>().trim().to_string())
                    })
            })
            .or_else(|| {
                Selector::parse("title").ok().and_then(|selector| {
                    document.select(&selector).next().map(|el| {
                        el.text()
                            .collect::<String>()
                            .trim()
                            .trim_end_matches(" - Wikipedia")
                            .to_string()
                    })
                })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find article title".to_string(),
            })?;

        // Wikipedia articles don't have a single author, so we leave it as None
        // The source is "wikipedia.org"
        let source = url
            .host_str()
            .map(|h| h.to_string())
            .unwrap_or_else(|| "wikipedia.org".to_string());

        Ok(Entry::new(
            title,
            url.to_string(),
            source,
            ContentType::Article,
        ))
    }
}

impl MetadataExtractor for WikipediaExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str()
            .map(|host| {
                host == "wikipedia.org"
                    || host.ends_with(".wikipedia.org")
                    || host == "en.m.wikipedia.org"
            })
            .unwrap_or(false)
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
