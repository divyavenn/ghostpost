use crate::models::Entry;

/// Format a metadata header from an Entry.
///
/// Returns a markdown header with title, author/director, year, and starring
/// fields (only includes fields that are present). Returns `None` if the entry
/// has no displayable metadata.
pub fn format_metadata_header(entry: &Entry) -> Option<String> {
    let mut lines = Vec::new();

    let title = entry.title.trim();
    if !title.is_empty() {
        lines.push(format!("# {}", title));
        lines.push(String::new());
    }

    let url = entry.url.trim();
    if !url.is_empty() {
        lines.push(format!("- **Source:** {}", url));
    }

    if let Some(ref a) = entry.author {
        lines.push(format!("- **Author:** {}", a));
    }
    if let Some(ref d) = entry.director {
        lines.push(format!("- **Director:** {}", d));
    }
    if let Some(y) = entry.year {
        lines.push(format!("- **Year:** {}", y));
    }
    if let Some(ref s) = entry.starring {
        if !s.is_empty() {
            lines.push(format!("- **Starring:** {}", s.join(", ")));
        }
    }

    if lines.is_empty() {
        None
    } else {
        Some(lines.join("\n"))
    }
}
