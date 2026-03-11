use crate::error::Result;
use crate::models::{ContentType, Diary, DiaryDate, Entry};
use chrono::{Datelike, Local, NaiveDate};
use regex::Regex;
use std::fs;
use std::path::Path;

/// Load diary from file or create new if doesn't exist
pub fn load_diary(path: &Path) -> Result<Diary> {
    if !path.exists() {
        return Ok(Diary::new());
    }

    let content = fs::read_to_string(path)?;
    Ok(parse_diary(&content))
}

/// Try to parse an informal date string like "Feb 3", "Jan 21st", "January 15th"
/// with an explicit year context
fn parse_informal_date_with_year(text: &str, year: i32) -> Option<NaiveDate> {
    let text = text.trim();

    // Month name mappings
    let months: &[(&str, u32)] = &[
        ("jan", 1),
        ("january", 1),
        ("feb", 2),
        ("february", 2),
        ("mar", 3),
        ("march", 3),
        ("apr", 4),
        ("april", 4),
        ("may", 5),
        ("jun", 6),
        ("june", 6),
        ("jul", 7),
        ("july", 7),
        ("aug", 8),
        ("august", 8),
        ("sep", 9),
        ("sept", 9),
        ("september", 9),
        ("oct", 10),
        ("october", 10),
        ("nov", 11),
        ("november", 11),
        ("dec", 12),
        ("december", 12),
    ];

    let lower = text.to_lowercase();

    // Try to find month
    let mut month_num: Option<u32> = None;
    let mut remaining = &lower[..];

    for (name, num) in months {
        if lower.starts_with(name) {
            month_num = Some(*num);
            remaining = lower[name.len()..].trim_start();
            break;
        }
    }

    let month = month_num?;

    // Extract day number (remove ordinal suffixes like st, nd, rd, th)
    let day_re = Regex::new(r"^(\d{1,2})(?:st|nd|rd|th)?\s*$").ok()?;
    let cap = day_re.captures(remaining)?;
    let day: u32 = cap[1].parse().ok()?;

    NaiveDate::from_ymd_opt(year, month, day)
}

/// Parse diary content from string
pub fn parse_diary(content: &str) -> Diary {
    let mut diary = Diary::new();
    let mut current_date: Option<DiaryDate> = None;
    let mut preamble_lines: Vec<String> = Vec::new();
    let mut found_first_date = false;

    // Track current year context (default to current year)
    let mut current_year = Local::now().year();

    // Year header format: ### YYYY
    let year_re = Regex::new(r"^###\s+(\d{4})\s*$").unwrap();
    // Standard format: ## YYYY-MM-DD
    let date_re = Regex::new(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$").unwrap();
    // Informal format: "Feb 3", "Jan 21st", "January 15th" (with optional ## prefix)
    let informal_date_re =
        Regex::new(r"^(?:##\s+)?([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*$").unwrap();
    // Match both ", by author" and " - author" formats for backwards compatibility
    let entry_re =
        Regex::new(r"^\s*-\s+\[([^\]]+)\]\(([^\)]+)\)(?:(?:,\s*by\s+|\s+-\s+)(.+))?\s*$").unwrap();

    for line in content.lines() {
        // Check for year header first
        if let Some(cap) = year_re.captures(line) {
            if let Ok(year) = cap[1].parse::<i32>() {
                // Save current date before changing year context
                if let Some(date) = current_date.take() {
                    diary.dates.push(date);
                }
                current_year = year;
                found_first_date = true; // Year header counts as finding structure
            }
            continue;
        }

        // Try standard date format (## YYYY-MM-DD)
        if let Some(cap) = date_re.captures(line) {
            if let Some(date) = current_date.take() {
                diary.dates.push(date);
            }

            let date_str = &cap[1];
            match NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                Ok(date) => {
                    current_date = Some(DiaryDate::new(date));
                    found_first_date = true;
                }
                Err(e) => {
                    eprintln!("Warning: Failed to parse date '{}': {}", date_str, e);
                }
            }
            continue;
        }

        // Try informal date format (uses current_year context)
        if let Some(cap) = informal_date_re.captures(line) {
            let month_str = &cap[1];
            let day_str = &cap[2];
            let informal_str = format!("{} {}", month_str, day_str);

            if let Some(date) = parse_informal_date_with_year(&informal_str, current_year) {
                if let Some(prev_date) = current_date.take() {
                    diary.dates.push(prev_date);
                }
                current_date = Some(DiaryDate::new(date));
                found_first_date = true;
                continue;
            }
        }

        if let Some(cap) = entry_re.captures(line) {
            if let Some(ref mut date) = current_date {
                let title = cap[1].to_string();
                let url_str = cap[2].to_string();
                let author = cap.get(3).map(|m| m.as_str().to_string());

                // Try to extract source from URL
                let source = url::Url::parse(&url_str)
                    .ok()
                    .and_then(|u| u.host_str().map(|s| s.to_string()))
                    .unwrap_or_else(|| "unknown".to_string());

                let mut entry = Entry::new(title, url_str, source, ContentType::Unknown);
                if let Some(a) = author {
                    entry = entry.with_author(a);
                }
                date.add_entry(entry);
            }
            continue;
        }

        // Handle plain text entries without URLs (e.g., "- Wuthering Heights", "- The Materialists")
        let plain_entry_re = Regex::new(r"^\s*-\s+([^\[\]]+?)(?:,\s*by\s+(.+))?\s*$").unwrap();
        if let Some(cap) = plain_entry_re.captures(line) {
            if let Some(ref mut date) = current_date {
                let title = cap[1].trim().to_string();
                // Skip if title looks like a URL or markdown link
                if !title.starts_with('[') && !title.starts_with("http") && !title.is_empty() {
                    let author = cap.get(2).map(|m| m.as_str().trim().to_string());
                    let mut entry = Entry::new(
                        title,
                        String::new(),
                        "local".to_string(),
                        ContentType::Unknown,
                    );
                    if let Some(a) = author {
                        entry = entry.with_author(a);
                    }
                    date.add_entry(entry);
                }
            }
            continue;
        }

        if !found_first_date && !line.trim().is_empty() {
            preamble_lines.push(line.to_string());
        }
    }

    if let Some(date) = current_date {
        diary.dates.push(date);
    }

    if !preamble_lines.is_empty() {
        diary.preamble = Some(preamble_lines.join("\n"));
    }

    diary.dates.sort_by(|a, b| b.date.cmp(&a.date));

    diary
}

/// Insert an entry into the diary for a specific date
pub fn insert_entry(diary: &mut Diary, date: NaiveDate, entry: Entry) {
    match diary
        .dates
        .binary_search_by(|probe| probe.date.cmp(&date).reverse())
    {
        Ok(index) => {
            diary.dates[index].add_entry(entry);
        }
        Err(index) => {
            let mut diary_date = DiaryDate::new(date);
            diary_date.add_entry(entry);
            diary.dates.insert(index, diary_date);
        }
    }
}

/// Save diary to file
pub fn save_diary(diary: &Diary, path: &Path) -> Result<()> {
    let content = serialize_diary(diary);

    let temp_path = path.with_extension("tmp");
    fs::write(&temp_path, content)?;
    fs::rename(&temp_path, path)?;

    Ok(())
}

/// Format a date informally (e.g., "Feb 4" or "Jan 21")
fn format_informal_date(date: NaiveDate) -> String {
    let month = match date.month() {
        1 => "Jan",
        2 => "Feb",
        3 => "Mar",
        4 => "Apr",
        5 => "May",
        6 => "Jun",
        7 => "Jul",
        8 => "Aug",
        9 => "Sep",
        10 => "Oct",
        11 => "Nov",
        12 => "Dec",
        _ => "???",
    };
    format!("{} {}", month, date.day())
}

/// Serialize diary to markdown string
pub fn serialize_diary(diary: &Diary) -> String {
    let mut lines = Vec::new();

    if let Some(ref preamble) = diary.preamble {
        lines.push(preamble.clone());
        lines.push(String::new());
    }

    let this_year = Local::now().year();
    let mut current_year: Option<i32> = None;

    for diary_date in &diary.dates {
        let entry_year = diary_date.date.year();

        // Add year header only for past years (not current year)
        if current_year != Some(entry_year) {
            if entry_year != this_year {
                if current_year.is_some() {
                    // Add extra blank line before new year section
                    lines.push(String::new());
                }
                lines.push(format!("### {}", entry_year));
                lines.push(String::new());
            }
            current_year = Some(entry_year);
        }

        // Use informal date format (e.g., "Feb 4")
        lines.push(format_informal_date(diary_date.date));

        for entry in &diary_date.entries {
            lines.push(format_entry(entry));
        }

        lines.push(String::new());
    }

    lines.join("\n")
}

/// Format a diary entry based on its content type.
fn format_entry(entry: &Entry) -> String {
    let escaped_title = escape_markdown(&entry.title);
    let has_url = !entry.url.is_empty();

    match entry.content_type {
        // Movies/TV shows: "- [Title](URL) (Year) directed by Director"
        ContentType::Movie | ContentType::TVShow => {
            let mut parts = if has_url {
                format!("- [{}]({})", escaped_title, entry.url)
            } else {
                format!("- {}", escaped_title)
            };
            if let Some(y) = entry.year {
                parts.push_str(&format!(" ({})", y));
            }
            if let Some(ref d) = entry.director {
                parts.push_str(&format!(" directed by {}", d));
            }
            parts
        }

        // Books: "- Title, by Author" (no URL — books don't have a single canonical link)
        ContentType::Book => {
            let mut parts = if has_url {
                format!("- [{}]({})", escaped_title, entry.url)
            } else {
                format!("- {}", escaped_title)
            };
            if let Some(ref author) = entry.author {
                parts.push_str(&format!(", by {}", author));
            }
            parts
        }

        // YouTube: "- [Title](URL) (video)"
        ContentType::YouTube => {
            if has_url {
                format!("- [{}]({}) (video)", escaped_title, entry.url)
            } else {
                format!("- {} (video)", escaped_title)
            }
        }

        // Tweets: "- [Title](URL) (thread)"
        ContentType::Tweet => {
            if has_url {
                format!("- [{}]({}) (thread)", escaped_title, entry.url)
            } else {
                format!("- {} (thread)", escaped_title)
            }
        }

        // Podcasts: "- [Title](URL) (podcast)"
        ContentType::Podcast => {
            if has_url {
                format!("- [{}]({}) (podcast)", escaped_title, entry.url)
            } else {
                format!("- {} (podcast)", escaped_title)
            }
        }

        // GitHub repos: "- [Title](URL) (repo)"
        ContentType::GitHub => {
            if has_url {
                format!("- [{}]({}) (repo)", escaped_title, entry.url)
            } else {
                format!("- {} (repo)", escaped_title)
            }
        }

        // Research papers: "- [Title](URL), by Author (paper)"
        ContentType::ResearchPaper => {
            let mut parts = if has_url {
                format!("- [{}]({})", escaped_title, entry.url)
            } else {
                format!("- {}", escaped_title)
            };
            if let Some(ref author) = entry.author {
                parts.push_str(&format!(", by {}", author));
            }
            parts.push_str(" (paper)");
            parts
        }

        // PDF: "- [Title](URL) (pdf)"
        ContentType::PDF => {
            if has_url {
                format!("- [{}]({}) (pdf)", escaped_title, entry.url)
            } else {
                format!("- {} (pdf)", escaped_title)
            }
        }

        // Article, Substack, Medium, Unknown: "- [Title](URL), by Author"
        _ => {
            if has_url {
                let mut line = format!("- [{}]({})", escaped_title, entry.url);
                if let Some(ref author) = entry.author {
                    line.push_str(&format!(", by {}", author));
                }
                line
            } else {
                let mut line = format!("- {}", escaped_title);
                if let Some(ref author) = entry.author {
                    line.push_str(&format!(", by {}", author));
                }
                line
            }
        }
    }
}

/// Escape markdown special characters in titles
fn escape_markdown(text: &str) -> String {
    text.replace('\\', "\\\\")
        .replace('[', "\\[")
        .replace(']', "\\]")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_escape_markdown() {
        assert_eq!(escape_markdown("Normal title"), "Normal title");
        assert_eq!(
            escape_markdown("Title [with] brackets"),
            "Title \\[with\\] brackets"
        );
        assert_eq!(
            escape_markdown("Title\\with\\backslash"),
            "Title\\\\with\\\\backslash"
        );
    }

    #[test]
    fn test_parse_empty_diary() {
        let diary = parse_diary("");
        assert_eq!(diary.dates.len(), 0);
    }

    #[test]
    fn test_parse_single_date() {
        let content = "## 2026-01-20\n- [Test](https://example.com), by Author";
        let diary = parse_diary(content);
        assert_eq!(diary.dates.len(), 1);
        assert_eq!(diary.dates[0].entries.len(), 1);
        assert_eq!(diary.dates[0].entries[0].title, "Test");
        assert_eq!(diary.dates[0].entries[0].author, Some("Author".to_string()));
    }

    #[test]
    fn test_parse_old_format() {
        let content = "## 2026-01-20\n- [Test](https://example.com) - Author";
        let diary = parse_diary(content);
        assert_eq!(diary.dates.len(), 1);
        assert_eq!(diary.dates[0].entries[0].author, Some("Author".to_string()));
    }

    #[test]
    fn test_insert_new_date() {
        let mut diary = Diary::new();
        let date = NaiveDate::from_ymd_opt(2026, 1, 20).unwrap();
        let entry = Entry::new(
            "Test".to_string(),
            "https://example.com".to_string(),
            "example.com".to_string(),
            ContentType::Article,
        );
        insert_entry(&mut diary, date, entry);
        assert_eq!(diary.dates.len(), 1);
    }

    #[test]
    fn test_insert_maintains_order() {
        let mut diary = Diary::new();

        let date1 = NaiveDate::from_ymd_opt(2026, 1, 20).unwrap();
        let date2 = NaiveDate::from_ymd_opt(2026, 1, 22).unwrap();
        let date3 = NaiveDate::from_ymd_opt(2026, 1, 18).unwrap();

        let entry = Entry::new(
            "Test".to_string(),
            "https://example.com".to_string(),
            "example.com".to_string(),
            ContentType::Article,
        );

        insert_entry(&mut diary, date1, entry.clone());
        insert_entry(&mut diary, date2, entry.clone());
        insert_entry(&mut diary, date3, entry);

        assert_eq!(diary.dates.len(), 3);
        assert_eq!(diary.dates[0].date, date2); // 2026-01-22
        assert_eq!(diary.dates[1].date, date1); // 2026-01-20
        assert_eq!(diary.dates[2].date, date3); // 2026-01-18
    }
}
