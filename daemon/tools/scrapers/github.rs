use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use regex::Regex;
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use serde_json::Value;
use url::Url;

use super::extractor::MetadataExtractor;

pub struct GitHubExtractor;

impl GitHubExtractor {
    pub fn new() -> Self {
        Self
    }

    fn extract_repo_info(&self, url: &Url) -> Option<(String, String)> {
        let path = url.path();
        let re = Regex::new(r"^/([^/]+)/([^/]+)").ok()?;
        re.captures(path).and_then(|cap| {
            let owner = cap.get(1)?.as_str().to_string();
            let repo = cap.get(2)?.as_str().to_string();
            Some((owner, repo))
        })
    }

    fn try_api(&self, owner: &str, repo: &str, client: &Client, url: &Url) -> Result<Entry> {
        let api_url = format!("https://api.github.com/repos/{}/{}", owner, repo);

        let response = client
            .get(&api_url)
            .header("User-Agent", "consumed/0.1.0")
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch GitHub API: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read API response: {}", e),
            })?;

        let data: Value =
            serde_json::from_str(&response).map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to parse GitHub API response: {}", e),
            })?;

        let name = data["name"]
            .as_str()
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find repo name in API response".to_string(),
            })?
            .to_string();

        let description = data["description"].as_str().map(|s| s.to_string());
        let owner_login = data["owner"]["login"].as_str().map(|s| s.to_string());

        let title = if let Some(desc) = &description {
            format!("{} - {}", name, desc)
        } else {
            name
        };

        let mut entry = Entry::new(
            title,
            url.to_string(),
            "github.com".to_string(),
            ContentType::GitHub,
        );
        if let Some(a) = owner_login {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }

    fn try_html(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .header("User-Agent", "consumed/0.1.0")
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch GitHub page: {}", e),
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
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find title in GitHub HTML".to_string(),
            })?;

        let description = Selector::parse("meta[property='og:description']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
            });

        let full_title = if let Some(desc) = description {
            format!("{} - {}", title, desc)
        } else {
            title.to_string()
        };

        let author = self.extract_repo_info(url).map(|(owner, _)| owner);

        let mut entry = Entry::new(
            full_title,
            url.to_string(),
            "github.com".to_string(),
            ContentType::GitHub,
        );
        if let Some(a) = author {
            entry = entry.with_author(a);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for GitHubExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str() == Some("github.com")
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        if let Some((owner, repo)) = self.extract_repo_info(url) {
            if let Ok(entry) = self.try_api(&owner, &repo, client, url) {
                return Ok(entry);
            }
        }
        self.try_html(url, client)
    }
}
