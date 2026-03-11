use clap::{Parser, Subcommand};

#[derive(Parser, Debug)]
#[command(name = "consumed")]
#[command(about = "Track consumed content in a markdown diary", long_about = None)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,

    /// Verbose output
    #[arg(short, long, global = true)]
    pub verbose: bool,
}

#[derive(Subcommand, Debug)]
pub enum Commands {
    /// Add a URL to your reading log
    Log {
        /// URL of the content (article, video, paper, repo)
        url: String,

        /// Date in YYYY-MM-DD format (defaults to today)
        date: Option<String>,

        /// Path to diary file (for local mode)
        #[arg(short, long, default_value = "reading_now.md")]
        diary_path: String,

        /// Commit to GitHub instead of local file
        #[arg(long)]
        github: bool,
    },

    /// Log URL and post to Substack Notes
    Post {
        /// URL of the content to share
        url: String,

        /// Optional quote from the content
        #[arg(short, long)]
        quote: Option<String>,

        /// Optional commentary/thoughts
        #[arg(short, long)]
        thoughts: Option<String>,

        /// Preview without posting
        #[arg(long)]
        dry_run: bool,

        /// Show browser window (don't run headless)
        #[arg(long)]
        no_headless: bool,
    },

    /// Login to Substack (one-time setup)
    Login,
}
