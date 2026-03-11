use crate::error::Result;
use crate::models::Entry;
use reqwest::blocking::Client;
use url::Url;

/// Trait for metadata extractors
pub trait MetadataExtractor {
    /// Check if this extractor can handle the given URL
    fn can_handle(&self, url: &Url) -> bool;

    /// Extract metadata from the URL
    fn extract(&self, url: &Url, client: &Client) -> Result<Entry>;
}
