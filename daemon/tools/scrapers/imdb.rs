use crate::error::{ConsumedError, Result};
use crate::models::{ContentType, Entry};
use regex::Regex;
use reqwest::blocking::Client;
use scraper::{Html, Selector};
use serde::Deserialize;
use url::Url;

use super::extractor::MetadataExtractor;

/// Subset of schema.org JSON-LD that IMDB embeds in every title page.
#[derive(Debug, Deserialize)]
struct ImdbJsonLd {
    name: Option<String>,
    director: Option<JsonLdPersonOrArray>,
    creator: Option<JsonLdPersonOrArray>,
    #[serde(rename = "datePublished")]
    date_published: Option<String>,
}

/// A person entry — IMDB emits either a single object or an array.
#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum JsonLdPersonOrArray {
    Single(JsonLdPerson),
    Multiple(Vec<JsonLdPerson>),
}

#[derive(Debug, Deserialize)]
struct JsonLdPerson {
    name: Option<String>,
    #[serde(rename = "@type")]
    ld_type: Option<String>,
}

impl ImdbJsonLd {
    fn first_person_name(field: &Option<JsonLdPersonOrArray>) -> Option<String> {
        match field {
            Some(JsonLdPersonOrArray::Single(p)) => {
                if p.ld_type.as_deref() == Some("Person") {
                    p.name.clone()
                } else {
                    None
                }
            }
            Some(JsonLdPersonOrArray::Multiple(v)) => v
                .iter()
                .find(|p| p.ld_type.as_deref() == Some("Person"))
                .and_then(|p| p.name.clone()),
            None => None,
        }
    }

    /// Director name, falling back to creator (for TV series that lack a director).
    fn director_or_creator(&self) -> Option<String> {
        Self::first_person_name(&self.director).or_else(|| Self::first_person_name(&self.creator))
    }

    /// Year from datePublished (e.g., "1995-09-24" or "1995").
    fn year(&self) -> Option<u16> {
        self.date_published
            .as_ref()
            .and_then(|d| d[..4].parse().ok())
    }
}

pub struct ImdbExtractor;

impl ImdbExtractor {
    pub fn new() -> Self {
        Self
    }

    /// Determine if this is a movie or TV show based on URL/content
    fn detect_content_type(&self, url: &Url, html: &str) -> ContentType {
        let path = url.path();

        // Check URL patterns
        if path.contains("/episodes") {
            return ContentType::TVShow;
        }

        // Check og:type meta tag
        let document = Html::parse_document(html);
        if let Ok(selector) = Selector::parse("meta[property='og:type']") {
            if let Some(el) = document.select(&selector).next() {
                if let Some(og_type) = el.value().attr("content") {
                    match og_type {
                        "video.tv_show" => return ContentType::TVShow, // TV series
                        "video.episode" => return ContentType::TVShow,
                        "video.movie" => return ContentType::Movie,
                        _ => {}
                    }
                }
            }
        }

        // Default to movie
        ContentType::Movie
    }

    fn extract_from_page(&self, url: &Url, client: &Client) -> Result<Entry> {
        let html = client
            .get(url.as_str())
            .header(
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            .header("Accept-Language", "en-US,en;q=0.9")
            .send()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to fetch IMDB page: {}", e),
            })?
            .text()
            .map_err(|e| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: format!("Failed to read response: {}", e),
            })?;

        let document = Html::parse_document(&html);

        // Parse JSON-LD for reliable structured data (title, director/creator, year)
        let json_ld = Selector::parse("script[type='application/ld+json']")
            .ok()
            .and_then(|selector| {
                for el in document.select(&selector) {
                    let json_text = el.text().collect::<String>();
                    if let Ok(ld) = serde_json::from_str::<ImdbJsonLd>(&json_text) {
                        if ld.name.is_some() {
                            return Some(ld);
                        }
                    }
                }
                None
            });

        // Title: prefer JSON-LD name (always clean), fall back to og:title with cleanup
        let clean_title = json_ld
            .as_ref()
            .and_then(|ld| ld.name.clone())
            .or_else(|| {
                Selector::parse("meta[property='og:title']")
                    .ok()
                    .and_then(|selector| {
                        document
                            .select(&selector)
                            .next()
                            .and_then(|el| el.value().attr("content"))
                            .map(|s| {
                                let s = s.trim_end_matches(" - IMDb");
                                let s = if let Some(idx) = s.find('⭐') {
                                    s[..idx].trim()
                                } else if let Some(idx) = s.find('|') {
                                    s[..idx].trim()
                                } else {
                                    s
                                };
                                // Strip parenthetical suffixes like "(2011)" or "(TV Mini Series 1995)"
                                let paren_re = Regex::new(r"\s*\([^)]*\d{4}[^)]*\)\s*$").unwrap();
                                paren_re.replace(s, "").trim().to_string()
                            })
                    })
            })
            .ok_or_else(|| ConsumedError::MetadataExtraction {
                url: url.to_string(),
                reason: "Could not find title".to_string(),
            })?;

        // Year: prefer og:title parenthetical (matches what users expect, e.g. "1995" for
        // a TV series that aired in 1995 even if datePublished says 1996), fall back to JSON-LD
        let year = Selector::parse("meta[property='og:title']")
            .ok()
            .and_then(|selector| {
                document
                    .select(&selector)
                    .next()
                    .and_then(|el| el.value().attr("content"))
                    .and_then(|s| {
                        let re = Regex::new(r"\((?:[^)]*?)(\d{4})\)").unwrap();
                        re.captures(s).and_then(|c| c[1].parse().ok())
                    })
            })
            .or_else(|| json_ld.as_ref().and_then(|ld| ld.year()));

        // Director/creator from JSON-LD
        let author = json_ld.as_ref().and_then(|ld| ld.director_or_creator());

        // Extract starring cast
        let starring = Selector::parse("a[data-testid=\"title-cast-item__actor\"]")
            .ok()
            .map(|selector| {
                document
                    .select(&selector)
                    .take(5)
                    .map(|el| el.text().collect::<String>().trim().to_string())
                    .filter(|s| !s.is_empty())
                    .collect::<Vec<String>>()
            })
            .filter(|v| !v.is_empty())
            .or_else(|| {
                // Fallback: collect a[href*="/name/"] that aren't the director
                Selector::parse("a[href*='/name/']").ok().map(|selector| {
                    document
                        .select(&selector)
                        .map(|el| el.text().collect::<String>().trim().to_string())
                        .filter(|name| {
                            !name.is_empty() && author.as_ref().map_or(true, |dir| name != dir)
                        })
                        .take(5)
                        .collect::<Vec<String>>()
                })
            })
            .filter(|v| !v.is_empty());

        let content_type = self.detect_content_type(url, &html);

        let mut entry = Entry::new(
            clean_title,
            url.to_string(),
            "imdb.com".to_string(),
            content_type,
        );
        if let Some(d) = author {
            entry = entry.with_director(d);
        }
        if let Some(y) = year {
            entry = entry.with_year(y);
        }
        if let Some(s) = starring {
            entry = entry.with_starring(s);
        }
        Ok(entry)
    }
}

impl MetadataExtractor for ImdbExtractor {
    fn can_handle(&self, url: &Url) -> bool {
        url.host_str()
            .map(|host| host == "imdb.com" || host == "www.imdb.com" || host == "m.imdb.com")
            .unwrap_or(false)
    }

    fn extract(&self, url: &Url, client: &Client) -> Result<Entry> {
        self.extract_from_page(url, client)
    }
}
