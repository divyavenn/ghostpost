use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};

const CDP_HTTP: &str = "http://127.0.0.1:9222";
const REDDIT_SEARCH_WEB: &str = "https://old.reddit.com/search";
const REDDIT_SEARCH_JSON: &str = "https://www.reddit.com/search.json";

#[derive(Debug, Clone)]
pub struct RedditResearchRequest {
    pub query: String,
    pub max_iterations: usize,
    pub max_posts_per_query: usize,
    pub max_comments_per_post: usize,
    pub min_unique_posts: usize,
}

impl RedditResearchRequest {
    pub fn from_payload(payload: &Value) -> Result<Self, String> {
        let query = payload
            .get("query")
            .and_then(Value::as_str)
            .or_else(|| payload.get("content").and_then(Value::as_str))
            .or_else(|| payload.get("url").and_then(Value::as_str))
            .unwrap_or("")
            .trim()
            .to_string();

        if query.is_empty() {
            return Err("Missing required 'query' in task payload".to_string());
        }

        Ok(Self {
            query,
            max_iterations: payload
                .get("max_iterations")
                .and_then(Value::as_u64)
                .map(|v| v as usize)
                .unwrap_or(6)
                .clamp(1, 12),
            max_posts_per_query: payload
                .get("max_posts_per_query")
                .and_then(Value::as_u64)
                .map(|v| v as usize)
                .unwrap_or(8)
                .clamp(1, 25),
            max_comments_per_post: payload
                .get("max_comments_per_post")
                .and_then(Value::as_u64)
                .map(|v| v as usize)
                .unwrap_or(5)
                .clamp(1, 20),
            min_unique_posts: payload
                .get("min_unique_posts")
                .and_then(Value::as_u64)
                .map(|v| v as usize)
                .unwrap_or(10)
                .clamp(3, 50),
        })
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct RedditComment {
    pub author: String,
    pub body: String,
    pub score: i64,
    pub permalink: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RedditPostFinding {
    pub query: String,
    pub subreddit: Option<String>,
    pub title: String,
    pub url: String,
    pub score: Option<i64>,
    pub snippet: Option<String>,
    pub relevant_comments: Vec<RedditComment>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RedditResearchResult {
    pub query: String,
    pub attempted_queries: Vec<String>,
    pub adequately_answered: bool,
    pub unique_post_count: usize,
    pub relevant_comment_count: usize,
    pub findings: Vec<RedditPostFinding>,
}

#[derive(Debug, Deserialize)]
struct CdpTargetResponse {
    #[serde(rename = "id")]
    target_id: String,
}

pub async fn research_reddit_via_cdp(
    request: RedditResearchRequest,
) -> Result<RedditResearchResult, String> {
    let http = Client::new();

    let base_keywords = query_keywords(&request.query);
    let mut query_queue = seed_queries(&request.query);
    let mut attempted: Vec<String> = Vec::new();
    let mut seen_posts: HashSet<String> = HashSet::new();
    let mut findings: Vec<RedditPostFinding> = Vec::new();
    let mut discovered_subreddits: HashSet<String> = HashSet::new();

    for _ in 0..request.max_iterations {
        let Some(next_query) = next_unattempted_query(&mut query_queue, &attempted) else {
            break;
        };
        attempted.push(next_query.clone());

        let cdp_tab = open_search_in_browser_via_cdp(&http, &next_query).await;

        let posts = search_posts_json(&http, &next_query, request.max_posts_per_query).await;
        let mut new_posts_this_round = 0usize;

        for post in posts {
            if !seen_posts.insert(post.url.clone()) {
                continue;
            }
            new_posts_this_round += 1;

            if let Some(ref sub) = post.subreddit {
                discovered_subreddits.insert(sub.clone());
            }

            let comments = fetch_relevant_comments(
                &http,
                &post.url,
                &base_keywords,
                request.max_comments_per_post,
            )
            .await;

            findings.push(RedditPostFinding {
                query: next_query.clone(),
                subreddit: post.subreddit,
                title: post.title,
                url: post.url,
                score: post.score,
                snippet: post.snippet,
                relevant_comments: comments,
            });
        }

        if let Some(target_id) = cdp_tab {
            let _ = close_cdp_target(&http, &target_id).await;
        }

        if is_adequately_answered(&findings, request.min_unique_posts) {
            break;
        }

        if new_posts_this_round == 0 {
            query_queue.extend(subreddit_expansions(&request.query, &discovered_subreddits));
        } else {
            query_queue.extend(facet_expansions(&request.query));
        }
    }

    let relevant_comment_count = findings.iter().map(|f| f.relevant_comments.len()).sum();
    let adequately_answered = is_adequately_answered(&findings, request.min_unique_posts);

    Ok(RedditResearchResult {
        query: request.query,
        attempted_queries: attempted,
        adequately_answered,
        unique_post_count: findings.len(),
        relevant_comment_count,
        findings,
    })
}

async fn open_search_in_browser_via_cdp(client: &Client, query: &str) -> Option<String> {
    let mut url = reqwest::Url::parse(REDDIT_SEARCH_WEB).ok()?;
    url.query_pairs_mut()
        .append_pair("q", query)
        .append_pair("sort", "relevance")
        .append_pair("t", "year");

    let endpoint = format!("{}/json/new?{}", CDP_HTTP, url.as_str());
    let response = client.put(endpoint).send().await.ok()?;
    let parsed: CdpTargetResponse = response.json().await.ok()?;
    Some(parsed.target_id)
}

async fn close_cdp_target(client: &Client, target_id: &str) -> bool {
    client
        .get(format!("{}/json/close/{}", CDP_HTTP, target_id))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

#[derive(Debug)]
struct SearchPost {
    title: String,
    url: String,
    subreddit: Option<String>,
    score: Option<i64>,
    snippet: Option<String>,
}

async fn search_posts_json(client: &Client, query: &str, limit: usize) -> Vec<SearchPost> {
    let response = match client
        .get(REDDIT_SEARCH_JSON)
        .query(&[
            ("q", query),
            ("sort", "relevance"),
            ("t", "year"),
            ("limit", &limit.to_string()),
            ("type", "link"),
        ])
        .header("User-Agent", "ghostpost/0.1 reddit-research")
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return vec![],
    };

    let body: Value = match response.json().await {
        Ok(v) => v,
        Err(_) => return vec![],
    };

    body.get("data")
        .and_then(|v| v.get("children"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|child| child.get("data").cloned())
        .filter_map(|data| {
            let permalink = data.get("permalink")?.as_str()?.to_string();
            let title = data.get("title")?.as_str()?.trim().to_string();
            if title.is_empty() {
                return None;
            }
            Some(SearchPost {
                title,
                url: format!("https://www.reddit.com{}", permalink),
                subreddit: data
                    .get("subreddit")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                score: data.get("score").and_then(Value::as_i64),
                snippet: data
                    .get("selftext")
                    .and_then(Value::as_str)
                    .map(|s| s.chars().take(280).collect::<String>())
                    .filter(|s| !s.is_empty()),
            })
        })
        .collect()
}

fn query_keywords(query: &str) -> Vec<String> {
    query
        .split_whitespace()
        .map(|s| s.to_lowercase())
        .map(|s| s.trim_matches(|c: char| !c.is_alphanumeric()).to_string())
        .filter(|s| s.len() >= 4)
        .collect::<HashSet<_>>()
        .into_iter()
        .collect()
}

fn seed_queries(query: &str) -> Vec<String> {
    let mut out = vec![query.to_string()];
    out.extend(facet_expansions(query));
    out
}

fn facet_expansions(query: &str) -> Vec<String> {
    [
        "feature requests",
        "pain points",
        "alternatives",
        "comparison",
        "workflow",
        "best tool",
    ]
    .iter()
    .map(|facet| format!("{} {}", query, facet))
    .collect()
}

fn subreddit_expansions(query: &str, subreddits: &HashSet<String>) -> Vec<String> {
    subreddits
        .iter()
        .take(6)
        .map(|s| format!("subreddit:{} {}", s, query))
        .collect()
}

fn next_unattempted_query(queue: &mut Vec<String>, attempted: &[String]) -> Option<String> {
    let attempted_set: HashSet<&str> = attempted.iter().map(|s| s.as_str()).collect();
    while let Some(candidate) = queue.first().cloned() {
        queue.remove(0);
        if !attempted_set.contains(candidate.as_str()) {
            return Some(candidate);
        }
    }
    None
}

fn is_adequately_answered(findings: &[RedditPostFinding], min_unique_posts: usize) -> bool {
    let post_count = findings.len();
    let comment_count: usize = findings.iter().map(|f| f.relevant_comments.len()).sum();
    post_count >= min_unique_posts && comment_count >= 10
}

fn extract_permalink_path(post_url: &str) -> Option<String> {
    let trimmed = post_url
        .trim_start_matches("https://www.reddit.com")
        .trim_start_matches("https://reddit.com")
        .trim_start_matches("http://www.reddit.com")
        .trim_start_matches("http://reddit.com");

    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

async fn fetch_relevant_comments(
    client: &Client,
    post_url: &str,
    keywords: &[String],
    max_comments: usize,
) -> Vec<RedditComment> {
    let Some(path) = extract_permalink_path(post_url) else {
        return vec![];
    };
    let json_url = format!("https://www.reddit.com{}.json?limit=30&sort=top", path);

    let response = match client
        .get(json_url)
        .header("User-Agent", "ghostpost/0.1 reddit-research")
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return vec![],
    };

    let body: Value = match response.json().await {
        Ok(v) => v,
        Err(_) => return vec![],
    };

    let comments = body
        .as_array()
        .and_then(|arr| arr.get(1))
        .and_then(|v| v.get("data"))
        .and_then(|v| v.get("children"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    let mut ranked: Vec<(usize, RedditComment)> = comments
        .into_iter()
        .filter_map(|child| child.get("data").cloned())
        .filter_map(|data| {
            let body = data.get("body")?.as_str()?.trim().to_string();
            if body.is_empty() {
                return None;
            }
            let lower = body.to_lowercase();
            let keyword_hits = keywords
                .iter()
                .filter(|k| lower.contains(k.as_str()))
                .count();
            if keyword_hits == 0 {
                return None;
            }
            Some((
                keyword_hits,
                RedditComment {
                    author: data
                        .get("author")
                        .and_then(Value::as_str)
                        .unwrap_or("unknown")
                        .to_string(),
                    body: body.chars().take(600).collect::<String>(),
                    score: data.get("score").and_then(Value::as_i64).unwrap_or(0),
                    permalink: data
                        .get("permalink")
                        .and_then(Value::as_str)
                        .map(|s| format!("https://www.reddit.com{}", s)),
                },
            ))
        })
        .collect();

    ranked.sort_by(|(a_hits, a), (b_hits, b)| b_hits.cmp(a_hits).then(b.score.cmp(&a.score)));
    ranked
        .into_iter()
        .take(max_comments)
        .map(|(_, c)| c)
        .collect()
}

pub fn summarize_findings(findings: &[RedditPostFinding]) -> Value {
    let mut subreddits: HashMap<String, usize> = HashMap::new();
    for finding in findings {
        if let Some(sub) = &finding.subreddit {
            *subreddits.entry(sub.clone()).or_insert(0) += 1;
        }
    }
    let mut subreddit_counts: Vec<(String, usize)> = subreddits.into_iter().collect();
    subreddit_counts.sort_by(|a, b| b.1.cmp(&a.1));

    json!({
        "top_subreddits": subreddit_counts.into_iter().take(10).collect::<Vec<_>>(),
        "sample_titles": findings.iter().take(10).map(|f| f.title.clone()).collect::<Vec<_>>(),
    })
}
