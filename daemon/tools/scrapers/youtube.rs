use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct YouTubeExtractor;

impl YouTubeExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_from_page(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch YouTube page: {}", e),
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
                Selector::parse("title")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .map(|el| el.text().collect::<String>())
                    })
                    .map(|s| s.replace(" - YouTube", "").trim().to_string())
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find video title".to_string(),
            })?;

        let author = Selector::parse("meta[name='author']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
            })
            .or_else(|| {
                Selector::parse("link[itemprop='name']")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .and_then(|el| el.value().attr("content"))
                    })
            })
            .map(|s| s.to_string());

        let mut entry = Entry::new(
            title,
            url.to_string(),
            "youtube.com".to_string(),
            ContentType::YouTube,
        );
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for YouTubeExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        matches!(
            url.host_str(),
            Some("youtube.com")
                | Some("www.youtube.com")
                | Some("m.youtube.com")
                | Some("youtu.be")
        )
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
