//! Task queue with SQLite persistence.

use chrono::{DateTime, Utc};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use uuid::Uuid;

/// User-facing task commands accepted by the /enqueue endpoint
pub const AVAILABLE_COMMANDS: &[&str] = &[
    "post_all",
    "post_x",
    "post_twitter",
    "post_substack",
    "post_linkedin",
    "reply_x",
    "search_x",
    "get_thread_x",
    "fetch_home_timeline_x",
    "fetch_user_timeline_x",
    "deep_scrape_thread_x",
    "shallow_scrape_thread_x",
    "scrape_tweets_x",
    "research_reddit",
];

#[derive(Debug, Clone, Serialize)]
pub struct TaskCommandDescriptor {
    pub command: String,
    pub task_types: Vec<String>,
    pub implemented: bool,
    pub description: String,
}

pub fn supported_task_commands() -> Vec<TaskCommandDescriptor> {
    vec![
        TaskCommandDescriptor {
            command: "post_all".to_string(),
            task_types: vec![
                "post_substack_note".to_string(),
                "post_tweet".to_string(),
                "post_linkedin".to_string(),
            ],
            implemented: true,
            description: "Queue post tasks for all enabled platforms".to_string(),
        },
        TaskCommandDescriptor {
            command: "post_x".to_string(),
            task_types: vec!["post_tweet".to_string()],
            implemented: true,
            description: "Queue a post on X/Twitter".to_string(),
        },
        TaskCommandDescriptor {
            command: "post_substack".to_string(),
            task_types: vec!["post_substack_note".to_string()],
            implemented: true,
            description: "Queue a Substack note".to_string(),
        },
        TaskCommandDescriptor {
            command: "post_linkedin".to_string(),
            task_types: vec!["post_linkedin".to_string()],
            implemented: true,
            description: "Queue a LinkedIn post".to_string(),
        },
        TaskCommandDescriptor {
            command: "reply_x".to_string(),
            task_types: vec!["reply_x".to_string()],
            implemented: false,
            description: "Reply to a tweet on X".to_string(),
        },
        TaskCommandDescriptor {
            command: "search_x".to_string(),
            task_types: vec!["search_x".to_string()],
            implemented: false,
            description: "Search tweets on X".to_string(),
        },
        TaskCommandDescriptor {
            command: "get_thread_x".to_string(),
            task_types: vec!["get_thread_x".to_string()],
            implemented: false,
            description: "Fetch thread context/replies on X".to_string(),
        },
        TaskCommandDescriptor {
            command: "fetch_home_timeline_x".to_string(),
            task_types: vec!["fetch_home_timeline_x".to_string()],
            implemented: false,
            description: "Fetch authenticated home timeline from X".to_string(),
        },
        TaskCommandDescriptor {
            command: "fetch_user_timeline_x".to_string(),
            task_types: vec!["fetch_user_timeline_x".to_string()],
            implemented: false,
            description: "Fetch a user's timeline from X".to_string(),
        },
        TaskCommandDescriptor {
            command: "deep_scrape_thread_x".to_string(),
            task_types: vec!["deep_scrape_thread_x".to_string()],
            implemented: false,
            description: "Deep scrape thread metrics and full replies".to_string(),
        },
        TaskCommandDescriptor {
            command: "shallow_scrape_thread_x".to_string(),
            task_types: vec!["shallow_scrape_thread_x".to_string()],
            implemented: false,
            description: "Lightweight thread metrics scrape".to_string(),
        },
        TaskCommandDescriptor {
            command: "scrape_tweets_x".to_string(),
            task_types: vec!["scrape_tweets_x".to_string()],
            implemented: false,
            description: "Run discovery scrape across accounts/queries".to_string(),
        },
        TaskCommandDescriptor {
            command: "research_reddit".to_string(),
            task_types: vec!["research_reddit".to_string()],
            implemented: true,
            description: "Research a topic on Reddit with CDP-driven iterative search".to_string(),
        },
    ]
}

/// Task types that can be queued
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum TaskType {
    PostSubstackNote,
    PostTweet,
    PostLinkedIn,
    ReplyX,
    SearchX,
    GetThreadX,
    FetchHomeTimelineX,
    FetchUserTimelineX,
    DeepScrapeThreadX,
    ShallowScrapeThreadX,
    ScrapeTweetsX,
    ResearchReddit,
    ScrollTwitter,
    LogUrl,
    LogToGitHub,
}

impl TaskType {
    pub fn as_str(&self) -> &'static str {
        match self {
            TaskType::PostSubstackNote => "post_substack_note",
            TaskType::PostTweet => "post_tweet",
            TaskType::PostLinkedIn => "post_linkedin",
            TaskType::ReplyX => "reply_x",
            TaskType::SearchX => "search_x",
            TaskType::GetThreadX => "get_thread_x",
            TaskType::FetchHomeTimelineX => "fetch_home_timeline_x",
            TaskType::FetchUserTimelineX => "fetch_user_timeline_x",
            TaskType::DeepScrapeThreadX => "deep_scrape_thread_x",
            TaskType::ShallowScrapeThreadX => "shallow_scrape_thread_x",
            TaskType::ScrapeTweetsX => "scrape_tweets_x",
            TaskType::ResearchReddit => "research_reddit",
            TaskType::ScrollTwitter => "scroll_twitter",
            TaskType::LogUrl => "log_url",
            TaskType::LogToGitHub => "log_to_github",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "post_substack_note" => Some(TaskType::PostSubstackNote),
            "post_tweet" | "post_x" | "post_twitter" => Some(TaskType::PostTweet),
            "post_linkedin" => Some(TaskType::PostLinkedIn),
            "reply_x" | "reply_tweet" => Some(TaskType::ReplyX),
            "search_x" | "search_tweets" => Some(TaskType::SearchX),
            "get_thread_x" | "get_thread" => Some(TaskType::GetThreadX),
            "fetch_home_timeline_x" | "fetch_home_timeline" => Some(TaskType::FetchHomeTimelineX),
            "fetch_user_timeline_x" | "fetch_user_timeline" => Some(TaskType::FetchUserTimelineX),
            "deep_scrape_thread_x" | "deep_scrape_thread" => Some(TaskType::DeepScrapeThreadX),
            "shallow_scrape_thread_x" | "shallow_scrape_thread" => {
                Some(TaskType::ShallowScrapeThreadX)
            }
            "scrape_tweets_x" | "scrape_tweets" => Some(TaskType::ScrapeTweetsX),
            "research_reddit" | "reddit_research" => Some(TaskType::ResearchReddit),
            "scroll_twitter" => Some(TaskType::ScrollTwitter),
            "log_url" => Some(TaskType::LogUrl),
            "log_to_github" => Some(TaskType::LogToGitHub),
            _ => None,
        }
    }
}

/// Task status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Pending,
    Running,
    Completed,
    Failed,
    AuthRequired,
}

impl TaskStatus {
    fn as_str(&self) -> &'static str {
        match self {
            TaskStatus::Pending => "pending",
            TaskStatus::Running => "running",
            TaskStatus::Completed => "completed",
            TaskStatus::Failed => "failed",
            TaskStatus::AuthRequired => "auth_required",
        }
    }

    fn from_str(s: &str) -> Option<Self> {
        match s {
            "pending" => Some(TaskStatus::Pending),
            "running" => Some(TaskStatus::Running),
            "completed" => Some(TaskStatus::Completed),
            "failed" => Some(TaskStatus::Failed),
            "auth_required" => Some(TaskStatus::AuthRequired),
            _ => None,
        }
    }
}

/// A task in the queue
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub task_type: TaskType,
    pub status: TaskStatus,
    pub payload: serde_json::Value,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub scheduled_for: Option<DateTime<Utc>>,
    pub retry_count: i32,
    pub max_retries: i32,
}

/// Request to create a new task
#[derive(Debug, Clone, Deserialize)]
pub struct CreateTaskRequest {
    pub task_type: TaskType,
    pub payload: serde_json::Value,
    #[serde(default)]
    pub scheduled_for: Option<DateTime<Utc>>,
    #[serde(default = "default_max_retries")]
    pub max_retries: i32,
}

fn default_max_retries() -> i32 {
    3
}

/// Task queue backed by SQLite
pub struct TaskQueue {
    conn: Arc<Mutex<Connection>>,
}

impl TaskQueue {
    /// Create a new task queue, initializing the database
    pub fn new(db_path: PathBuf) -> Result<Self, String> {
        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create database directory: {}", e))?;
        }

        let conn =
            Connection::open(&db_path).map_err(|e| format!("Failed to open database: {}", e))?;

        // Create tables
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payload TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                scheduled_for TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3
            )",
            [],
        )
        .map_err(|e| format!("Failed to create tasks table: {}", e))?;

        // Create index for efficient queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            [],
        )
        .map_err(|e| format!("Failed to create index: {}", e))?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks(scheduled_for)",
            [],
        )
        .map_err(|e| format!("Failed to create index: {}", e))?;

        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
        })
    }

    /// Get the default database path
    pub fn default_db_path() -> PathBuf {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".consumed")
            .join("tasks.db")
    }

    /// Create a new task
    pub fn create_task(&self, request: CreateTaskRequest) -> Result<Task, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;

        let id = Uuid::new_v4().to_string();
        let now = Utc::now();
        let payload_str = serde_json::to_string(&request.payload)
            .map_err(|e| format!("Failed to serialize payload: {}", e))?;

        conn.execute(
            "INSERT INTO tasks (id, task_type, status, payload, created_at, updated_at, scheduled_for, max_retries)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                id,
                request.task_type.as_str(),
                TaskStatus::Pending.as_str(),
                payload_str,
                now.to_rfc3339(),
                now.to_rfc3339(),
                request.scheduled_for.map(|d| d.to_rfc3339()),
                request.max_retries,
            ],
        )
        .map_err(|e| format!("Failed to insert task: {}", e))?;

        Ok(Task {
            id,
            task_type: request.task_type,
            status: TaskStatus::Pending,
            payload: request.payload,
            result: None,
            error: None,
            created_at: now,
            updated_at: now,
            scheduled_for: request.scheduled_for,
            retry_count: 0,
            max_retries: request.max_retries,
        })
    }

    /// Get pending tasks (ready to execute)
    pub fn get_pending_tasks(&self) -> Result<Vec<Task>, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;
        let now = Utc::now().to_rfc3339();

        let mut stmt = conn
            .prepare(
                "SELECT id, task_type, status, payload, result, error, created_at, updated_at, scheduled_for, retry_count, max_retries
                 FROM tasks
                 WHERE status = 'pending'
                   AND (scheduled_for IS NULL OR scheduled_for <= ?1)
                 ORDER BY created_at ASC",
            )
            .map_err(|e| format!("Failed to prepare query: {}", e))?;

        let tasks = stmt
            .query_map([now], |row| Ok(self.row_to_task(row)))
            .map_err(|e| format!("Failed to query tasks: {}", e))?
            .filter_map(|r| r.ok())
            .filter_map(|t| t.ok())
            .collect();

        Ok(tasks)
    }

    /// Get all tasks with optional status filter
    pub fn get_tasks(&self, status: Option<TaskStatus>) -> Result<Vec<Task>, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;

        let query = match status {
            Some(ref s) => format!(
                "SELECT id, task_type, status, payload, result, error, created_at, updated_at, scheduled_for, retry_count, max_retries
                 FROM tasks WHERE status = '{}' ORDER BY created_at DESC",
                s.as_str()
            ),
            None => "SELECT id, task_type, status, payload, result, error, created_at, updated_at, scheduled_for, retry_count, max_retries
                     FROM tasks ORDER BY created_at DESC".to_string(),
        };

        let mut stmt = conn
            .prepare(&query)
            .map_err(|e| format!("Failed to prepare query: {}", e))?;

        let tasks = stmt
            .query_map([], |row| Ok(self.row_to_task(row)))
            .map_err(|e| format!("Failed to query tasks: {}", e))?
            .filter_map(|r| r.ok())
            .filter_map(|t| t.ok())
            .collect();

        Ok(tasks)
    }

    /// Get a single task by ID
    pub fn get_task(&self, id: &str) -> Result<Option<Task>, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;

        let mut stmt = conn
            .prepare(
                "SELECT id, task_type, status, payload, result, error, created_at, updated_at, scheduled_for, retry_count, max_retries
                 FROM tasks WHERE id = ?1",
            )
            .map_err(|e| format!("Failed to prepare query: {}", e))?;

        let task = stmt
            .query_row([id], |row| Ok(self.row_to_task(row)))
            .ok()
            .and_then(|t| t.ok());

        Ok(task)
    }

    /// Update task status
    pub fn update_task_status(
        &self,
        id: &str,
        status: TaskStatus,
        result: Option<serde_json::Value>,
        error: Option<String>,
    ) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;
        let now = Utc::now().to_rfc3339();
        let result_str = result.map(|r| serde_json::to_string(&r).unwrap_or_default());

        conn.execute(
            "UPDATE tasks SET status = ?1, result = ?2, error = ?3, updated_at = ?4 WHERE id = ?5",
            params![status.as_str(), result_str, error, now, id],
        )
        .map_err(|e| format!("Failed to update task: {}", e))?;

        Ok(())
    }

    /// Update a task's payload (e.g. to store generated content before posting)
    pub fn update_task_payload(&self, id: &str, payload: serde_json::Value) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;
        let now = Utc::now().to_rfc3339();
        let payload_str = serde_json::to_string(&payload)
            .map_err(|e| format!("Failed to serialize payload: {}", e))?;

        conn.execute(
            "UPDATE tasks SET payload = ?1, updated_at = ?2 WHERE id = ?3",
            params![payload_str, now, id],
        )
        .map_err(|e| format!("Failed to update task payload: {}", e))?;

        Ok(())
    }

    /// Increment retry count and optionally update status
    pub fn increment_retry(&self, id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;
        let now = Utc::now().to_rfc3339();

        // Get current retry count and max
        let (retry_count, max_retries): (i32, i32) = conn
            .query_row(
                "SELECT retry_count, max_retries FROM tasks WHERE id = ?1",
                [id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .map_err(|e| format!("Failed to get task: {}", e))?;

        let new_count = retry_count + 1;
        let new_status = if new_count >= max_retries {
            TaskStatus::Failed.as_str()
        } else {
            TaskStatus::Pending.as_str()
        };

        conn.execute(
            "UPDATE tasks SET retry_count = ?1, status = ?2, updated_at = ?3 WHERE id = ?4",
            params![new_count, new_status, now, id],
        )
        .map_err(|e| format!("Failed to update task: {}", e))?;

        Ok(new_count < max_retries)
    }

    /// Delete a task
    pub fn delete_task(&self, id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;

        let rows = conn
            .execute("DELETE FROM tasks WHERE id = ?1", [id])
            .map_err(|e| format!("Failed to delete task: {}", e))?;

        Ok(rows > 0)
    }

    /// Delete completed tasks older than specified days
    pub fn cleanup_old_tasks(&self, days: i64) -> Result<usize, String> {
        let conn = self.conn.lock().map_err(|e| format!("Lock error: {}", e))?;
        let cutoff = (Utc::now() - chrono::Duration::days(days)).to_rfc3339();

        let rows = conn
            .execute(
                "DELETE FROM tasks WHERE status IN ('completed', 'failed') AND updated_at < ?1",
                [cutoff],
            )
            .map_err(|e| format!("Failed to cleanup tasks: {}", e))?;

        Ok(rows)
    }

    /// Helper to convert a row to a Task
    fn row_to_task(&self, row: &rusqlite::Row) -> Result<Task, rusqlite::Error> {
        let task_type_str: String = row.get(1)?;
        let status_str: String = row.get(2)?;
        let payload_str: String = row.get(3)?;
        let result_str: Option<String> = row.get(4)?;
        let created_at_str: String = row.get(6)?;
        let updated_at_str: String = row.get(7)?;
        let scheduled_for_str: Option<String> = row.get(8)?;

        Ok(Task {
            id: row.get(0)?,
            task_type: TaskType::from_str(&task_type_str).unwrap_or(TaskType::LogUrl),
            status: TaskStatus::from_str(&status_str).unwrap_or(TaskStatus::Pending),
            payload: serde_json::from_str(&payload_str).unwrap_or(serde_json::Value::Null),
            result: result_str.and_then(|s| serde_json::from_str(&s).ok()),
            error: row.get(5)?,
            created_at: DateTime::parse_from_rfc3339(&created_at_str)
                .map(|d| d.with_timezone(&Utc))
                .unwrap_or_else(|_| Utc::now()),
            updated_at: DateTime::parse_from_rfc3339(&updated_at_str)
                .map(|d| d.with_timezone(&Utc))
                .unwrap_or_else(|_| Utc::now()),
            scheduled_for: scheduled_for_str
                .and_then(|s| DateTime::parse_from_rfc3339(&s).ok())
                .map(|d| d.with_timezone(&Utc)),
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
        })
    }
}

// Make TaskQueue cloneable for sharing across handlers
impl Clone for TaskQueue {
    fn clone(&self) -> Self {
        Self {
            conn: Arc::clone(&self.conn),
        }
    }
}
