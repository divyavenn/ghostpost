"""Utilities for fetching article content and converting it to Markdown."""

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple

import trafilatura


def fetch_article_markdown(
    url: str,
    *,
    html: str | None = None,
    include_comments: bool = False,
    return_metadata: bool = False,
) -> str | Tuple[str, Dict[str, Any]]:

    if not url or not isinstance(url, str):
        raise ValueError("A non-empty URL string is required")

    downloaded: Optional[str]
    if html:
        downloaded = html
    else:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ValueError(f"Failed to download article at {url}")

    metadata = trafilatura.extract_metadata(downloaded, default_url=url)

    markdown = trafilatura.extract(
        downloaded,
        include_comments=include_comments,
        output_format="markdown",
        include_images=False,
        favor_recall=True,
    )

    if not markdown:
        raise ValueError(f"No content could be extracted from {url}")

    result_markdown = markdown.strip()

    if return_metadata:
        metadata_dict = {
            'title': metadata.title if metadata else None,
            'author': metadata.author if metadata else None,
            'publishDate': str(metadata.date) if metadata and metadata.date else None,
            'url': url,
            'contentType': 'article',
        }
        return result_markdown, metadata_dict

    return result_markdown


__all__ = ["fetch_article_markdown"]