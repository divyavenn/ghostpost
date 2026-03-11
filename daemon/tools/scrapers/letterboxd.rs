use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct LetterboxdExtractor;

impl LetterboxdExtractor {
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
                reason: format!("Failed to fetch Letterboxd page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

        // Extract title - try og:title first
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
                // Try the film title heading
                Selector::parse("h1.headline-1").ok().and_then(|selector| {
                    document
                        .select(&selector)
                        .next()
                        .map(|el| el.text().collect::<String>().trim().to_string())
                })
            })
            .or_else(|| {
                // Try filmtitle span
                Selector::parse("span.filmtitle").ok().and_then(|selector| {
                    document
                        .select(&selector)
                        .next()
                        .map(|el| el.text().collect::<String>().trim().to_string())
                })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find movie title".to_string(),
            })?;

        // Try to extract director
        let author = Selector::parse("meta[name='twitter:data1']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
                    .map(|s| s.to_string())
            })
            .or_else(|| {
                // Try director link
                Selector::parse("a[href*='/director/']")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .map(|el| el.text().collect::<String>().trim().to_string())
                    })
            })
            .or_else(|| {
                // Try the crew section for director
                Selector::parse(".crew-list a").ok().and_then(|selector| {
                    document
                        .select(&selector)
                        .next()
                        .map(|el| el.text().collect::<String>().trim().to_string())
                })
            });

        let mut entry = Entry::new(
            title,
            url.to_string(),
            "letterboxd.com".to_string(),
            ContentType::Movie,
        );
        if let Some(d) = author {
            entry = entry.with_director(d);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for LetterboxdExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str()
            .map(|host| host == "letterboxd.com" || host == "www.letterboxd.com")
            .unwrap_or(false)
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
