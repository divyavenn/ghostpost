use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

/// Type of content being logged
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ContentType {
    Article,
    Book,
    Movie,
    #[serde(rename = "tv_show")]
    TVShow,
    Podcast,
    GitHub,
    ResearchPaper,
    PDF,
    YouTube,
    Substack,
    Medium,
    Tweet,
    Unknown,
}

impl std::fmt::Display for ContentType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ContentType::Article => write!(f, "article"),
            ContentType::Book => write!(f, "book"),
            ContentType::Movie => write!(f, "movie"),
            ContentType::TVShow => write!(f, "tv_show"),
            ContentType::Podcast => write!(f, "podcast"),
            ContentType::GitHub => write!(f, "github"),
            ContentType::ResearchPaper => write!(f, "research paper"),
            ContentType::PDF => write!(f, "pdf"),
            ContentType::YouTube => write!(f, "youtube"),
            ContentType::Substack => write!(f, "substack"),
            ContentType::Medium => write!(f, "medium"),
            ContentType::Tweet => write!(f, "tweet"),
            ContentType::Unknown => write!(f, "unknown"),
        }
    }
}

impl ContentType {
    /// Returns whether this content type has a Python scraper.
    pub fn has_scraper(&self) -> bool {
        matches!(
            self,
            ContentType::Article
                | ContentType::Medium
                | ContentType::Substack
                | ContentType::YouTube
                | ContentType::Tweet
                | ContentType::PDF
                | ContentType::ResearchPaper
        )
    }
}

/// Represents a single consumed content entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entry {
    /// Title of the content
    pub title: String,
    /// Author(s) of the content
    pub author: Option<String>,
    /// Director (for movies/TV shows)
    pub director: Option<String>,
    /// URL of the content
    pub url: String,
    /// Source domain (e.g., "arxiv.org", "github.com", "nytimes.com")
    pub source: String,
    /// Type of content
    pub content_type: ContentType,
    /// Release year (e.g., for movies)
    pub year: Option<u16>,
    /// Starring cast (e.g., for movies)
    pub starring: Option<Vec<String>>,
    /// Image URL (og:image, poster, cover art)
    pub image_url: Option<String>,
}

impl Entry {
    pub fn new(title: String, url: String, source: String, content_type: ContentType) -> Self {
        Self {
            title,
            author: None,
            director: None,
            url,
            source,
            content_type,
            year: None,
            starring: None,
            image_url: None,
        }
    }

    pub fn with_author(mut self, author: impl Into<String>) -> Self {
        self.author = Some(author.into());
        self
    }

    pub fn with_director(mut self, director: impl Into<String>) -> Self {
        self.director = Some(director.into());
        self
    }

    pub fn with_year(mut self, year: u16) -> Self {
        self.year = Some(year);
        self
    }

    pub fn with_starring(mut self, starring: Vec<String>) -> Self {
        self.starring = Some(starring);
        self
    }
}

/// A date with its associated entries
#[derive(Debug, Clone)]
pub struct DiaryDate {
    pub date: NaiveDate,
    pub entries: Vec<Entry>,
}

impl DiaryDate {
    pub fn new(date: NaiveDate) -> Self {
        Self {
            date,
            entries: Vec::new(),
        }
    }

    pub fn add_entry(&mut self, entry: Entry) {
        self.entries.push(entry);
    }
}

/// The complete diary with all dates and entries
#[derive(Debug, Clone)]
pub struct Diary {
    pub dates: Vec<DiaryDate>,
    pub preamble: Option<String>, // Any text before the first date
}

impl Diary {
    pub fn new() -> Self {
        Self {
            dates: Vec::new(),
            preamble: None,
        }
    }
}

impl Default for Diary {
    fn default() -> Self {
        Self::new()
    }
}
