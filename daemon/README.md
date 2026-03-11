# Consumed - Content Tracking CLI

A Rust CLI tool for tracking consumed content (articles, videos, papers, repos) in a markdown diary with automatic metadata extraction.

## Features

- **Automatic metadata extraction** from multiple content types:
  - Articles and blogs (Open Graph, meta tags)
  - YouTube videos (title, channel)
  - arXiv papers (title, authors via API)
  - GitHub repositories (name, description, owner via API)
  - Substack articles (title, author)

- **Chronological organization**: Entries are automatically sorted by date (newest first)
- **Smart date handling**: Appends to existing dates or inserts new dates in the correct position
- **Markdown format**: Simple, readable diary.md file

## Installation

### From Source

```bash
cargo install --path .
```

Or build manually:

```bash
cargo build --release
# Binary will be at target/release/consumed
```

## Usage

```bash
consumed <URL> <DATE> [OPTIONS]
```

### Arguments

- `<URL>`: URL of the content to track
- `<DATE>`: Date in YYYY-MM-DD format

### Options

- `-d, --diary-path <PATH>`: Path to diary file (default: diary.md)
- `-v, --verbose`: Enable verbose output
- `-h, --help`: Print help information

### Examples

```bash
# Add an article
consumed https://example.com/article 2026-01-20

# Add a YouTube video
consumed https://youtube.com/watch?v=dQw4w9WgXcQ 2026-01-20

# Add an arXiv paper
consumed https://arxiv.org/abs/2301.12345 2026-01-20

# Add a GitHub repo
consumed https://github.com/rust-lang/rust 2026-01-20

# Add a Substack article
consumed https://username.substack.com/p/post-slug 2026-01-20

# Use custom diary path
consumed https://example.com 2026-01-20 --diary-path ~/notes/reading.md

# Verbose mode
consumed https://example.com 2026-01-20 --verbose
```

## Diary Format

The tool maintains a `diary.md` file in the following format:

```markdown
## 2026-01-20
- [Article Title](https://example.com/article) - Author Name
- [Another Article](https://example.com/another) - Multiple Authors

## 2026-01-19
- [YouTube Video](https://youtube.com/watch?v=abc) - Channel Name
- [arXiv Paper](https://arxiv.org/abs/2301.12345) - Smith, J., Doe, J.

## 2026-01-18
- [GitHub Repo](https://github.com/user/repo) - user
```

### Format Rules

- Dates are level 2 markdown headers: `## YYYY-MM-DD`
- Entries are bullet list items: `- [Title](url) - Authors`
- Dates sorted newest first (most recent at top)
- Authors are optional (omitted if unavailable)
- Duplicate URLs allowed (you might re-read content)
- Special characters in titles are automatically escaped

## How It Works

1. **Parse arguments**: Validates URL and date format
2. **Extract metadata**: Fetches URL and extracts title, authors using specialized extractors
3. **Load diary**: Reads existing diary.md or creates new one
4. **Insert entry**: Binary search to find correct date position, append or insert new date
5. **Save diary**: Atomically writes updated diary back to file

### Metadata Extraction

The tool uses a priority chain of extractors:

1. **YouTube**: Detects YouTube URLs, extracts video title and channel
2. **arXiv**: Detects arXiv URLs, uses API for paper metadata
3. **GitHub**: Detects GitHub URLs, uses API for repo metadata
4. **Substack**: Detects Substack domains, extracts article metadata
5. **Article** (fallback): Generic extractor using Open Graph tags, meta tags, or HTML title

If extraction fails, the tool creates a minimal entry with the URL as the title.

## Error Handling

- **Network errors**: Retries once, then creates minimal entry
- **Invalid URL**: Clear error message with expected format
- **Invalid date**: Validates format (YYYY-MM-DD)
- **Malformed diary**: Parses what it can, preserves unparseable content
- **Missing metadata**: Gracefully degrades to URL-only entries

## Development

### Project Structure

```
src/
├── main.rs           # Entry point
├── lib.rs            # Library exports
├── cli.rs            # CLI argument parsing
├── diary.rs          # Diary file management
├── models.rs         # Data structures
├── error.rs          # Custom errors
└── metadata/
    ├── mod.rs        # Extraction coordinator
    ├── extractor.rs  # Extractor trait
    ├── article.rs    # Generic article extractor
    ├── youtube.rs    # YouTube extractor
    ├── arxiv.rs      # arXiv extractor
    ├── github.rs     # GitHub extractor
    └── substack.rs   # Substack extractor
```

### Running Tests

```bash
cargo test
```

### Building

```bash
# Debug build
cargo build

# Release build (optimized)
cargo build --release
```

## Dependencies

- `clap` - CLI argument parsing
- `reqwest` - HTTP client
- `scraper` - HTML parsing
- `webpage` - High-level webpage metadata extraction
- `url` - URL parsing and validation
- `chrono` - Date handling
- `regex` - Pattern matching
- `serde` + `serde_json` - JSON parsing
- `anyhow` + `thiserror` - Error handling
- `html-escape` - Markdown escaping

## License

MIT

## Contributing

Contributions welcome! Feel free to open issues or pull requests.
