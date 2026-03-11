use thiserror::Error;

#[derive(Debug, Error)]
pub enum ConsumedError {
    #[error("Invalid URL: {0}")]
    InvalidUrl(String),

    #[error("Network error: {0}")]
    Network(#[from] reqwest::Error),

    #[error("Failed to parse HTML: {0}")]
    HtmlParse(String),

    #[error("Failed to extract metadata from {url}: {reason}")]
    MetadataExtraction { url: String, reason: String },

    #[error("Invalid date format: {0}. Expected YYYY-MM-DD")]
    InvalidDate(String),

    #[error("Diary file error: {0}")]
    DiaryFile(#[from] std::io::Error),

    #[error("Failed to parse diary: {0}")]
    DiaryParse(String),

    #[error("Failed to write diary: {0}")]
    DiaryWrite(String),

    #[error("GitHub API error: {0}")]
    GitHub(String),

    #[error("Python error: {0}")]
    Python(String),
}

pub type Result<T> = std::result::Result<T, ConsumedError>;
