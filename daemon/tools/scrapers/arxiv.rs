use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use regex::Regex;
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use url::Url;

use super::extractor::MetadataExtractor;

pub struct ArXivExtractor;

impl ArXivExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_arxiv_id(&self, url: &Url) -> Option<String> {
        let path = url.path();
        let re = Regex::new(r"(\d{4}\.\d{4,5})").ok()?;
        re.captures(path)
            .and_then(|cap| cap.get(1))
            .map(|m| m.as_str().to_string())
    }

    fn try_api(&self, arxiv_id: &str, client: &Client, url: &Url) -> Result<Entry> {
        let api_url = format!("http://export.arxiv.org/api/query?id_list={}", arxiv_id);

        let xml = client
            .get(&api_url)
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch arXiv API: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read API response: {}", e),
            })?;

        let document = Html::parse_document(&xml);

        let title = Selector::parse("entry > title")
            .ok()
            .and_then(|selector| {
                document.select(&selector).next().map(|el| {
                    el.text()
                        .collect::<String>()
                        .split_whitespace()
                        .collect::<Vec<_>>()
                        .join(" ")
                })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find title in arXiv API response".to_string(),
            })?;

        let author = Selector::parse("entry > author > name")
            .ok()
            .and_then(|selector| {
                let author_list: Vec<String> = document
                    .select(&selector)
                    .map(|el| el.text().collect::<String>().trim().to_string())
                    .collect();

                if author_list.is_empty() {
                    None
                } else {
                    Some(author_list.join(", "))
                }
            });

        let mut entry = Entry::new(
            title,
            url.to_string(),
            "arxiv.org".to_string(),
            ContentType::ResearchPaper,
        );
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }

    fn try_html(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch arXiv page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

        let title = Selector::parse("meta[name='citation_title']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find title in arXiv HTML".to_string(),
            })?;

        let author = Selector::parse("meta[name='citation_author']")
            .ok()
            .and_then(|selector| {
                let author_list: Vec<String> = document
                    .select(&selector)
                    .filter_map(|el| el.value().attr("content").map(|s| s.to_string()))
                    .collect();

                if author_list.is_empty() {
                    None
                } else {
                    Some(author_list.join(", "))
                }
            });

        let mut entry = Entry::new(
            title.to_string(),
            url.to_string(),
            "arxiv.org".to_string(),
            ContentType::ResearchPaper,
        );
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for ArXivExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str() == Some("arxiv.org")
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        if let Some(arxiv_id) = self.extract_arxiv_id(url) {
            if let Ok(entry) = self.try_api(&arxiv_id, client, url) {
                return Ok(entry);
            }
        }
        self.try_html(url, client)
    }
}
