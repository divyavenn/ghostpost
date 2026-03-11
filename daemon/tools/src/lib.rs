pub mod diary;
pub mod error;
pub mod github;
pub mod models;
pub mod python;
#[path = "../scrapers/mod.rs"]
pub mod scrapers;
pub use scrapers as metadata;
