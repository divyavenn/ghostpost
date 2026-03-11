use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct SubstackExtractor;

impl SubstackExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_from_page(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch Substack page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

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
                Selector::parse("title").ok().and_then(|selector| {
                    document
                        .select(&selector)
                        .next()
                        .map(|el| el.text().collect::<String>())
                })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find article title".to_string(),
            })?;

        let author = Selector::parse("meta[property='article:author'], meta[property='og:article:author'], meta[name='author']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
            })
            .or_else(|| {
                Selector::parse("meta[property='author']")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .and_then(|el| el.value().attr("content"))
                    })
            })
            .map(|s| s.to_string());

        let source = url.host_str().unwrap_or("substack.com").to_string();

        let mut entry = Entry::new(title, url.to_string(), source, ContentType::Substack);
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for SubstackExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str()
            .map(|host| host.ends_with(".substack.com"))
            .unwrap_or(false)
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
