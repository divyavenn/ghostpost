"""LLM-based metadata extraction using Claude API."""

import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

import anthropic
from bs4 import BeautifulSoup


@dataclass
class ExtractedMetadata:
    title: str
    author: Optional[str]
    content_type: str  # article, book, movie, tv_show, podcast, etc.
    image_url: Optional[str] = None  # og:image for covers/posters


def clean_html_for_llm(html: str, max_chars: int = 15000) -> str:
    """Extract readable text from HTML, limiting size for LLM context."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    # Get text content
    text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple newlines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    # Truncate if too long
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... truncated ...]"

    return text


@dataclass
class StructuredData:
    """Structured data extracted from HTML before cleaning."""
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    json_ld: Optional[dict] = None


def extract_structured_data(html: str) -> StructuredData:
    """Extract og tags and JSON-LD before HTML is cleaned."""
    soup = BeautifulSoup(html, "html.parser")
    data = StructuredData()

    # Extract Open Graph tags
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        data.og_title = og_title["content"]

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content"):
        data.og_description = og_desc["content"]

    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        data.og_image = og_image["content"]

    # Fallback to twitter:image
    if not data.og_image:
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            data.og_image = twitter_image["content"]

    # Extract JSON-LD structured data
    json_ld_script = soup.find("script", attrs={"type": "application/ld+json"})
    if json_ld_script and json_ld_script.string:
        try:
            data.json_ld = json.loads(json_ld_script.string)
        except json.JSONDecodeError:
            pass

    return data


def extract_with_llm(html: str, url: str) -> ExtractedMetadata:
    """Use Claude to extract metadata from page content."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Extract structured data before cleaning HTML
    structured = extract_structured_data(html)

    # Clean HTML for context
    page_text = clean_html_for_llm(html)

    # Build context with structured data
    context_parts = [f"URL: {url}"]

    if structured.og_title:
        context_parts.append(f"og:title: {structured.og_title}")
    if structured.og_description:
        context_parts.append(f"og:description: {structured.og_description}")
    if structured.json_ld:
        # Extract key fields from JSON-LD
        ld = structured.json_ld
        if ld.get("name"):
            context_parts.append(f"JSON-LD name: {ld['name']}")
        if ld.get("@type"):
            context_parts.append(f"JSON-LD type: {ld['@type']}")
        if ld.get("author"):
            author = ld["author"]
            if isinstance(author, dict):
                context_parts.append(f"JSON-LD author: {author.get('name', author)}")
            elif isinstance(author, list):
                names = [a.get("name", str(a)) if isinstance(a, dict) else str(a) for a in author]
                context_parts.append(f"JSON-LD authors: {', '.join(names)}")
            else:
                context_parts.append(f"JSON-LD author: {author}")
        if ld.get("director"):
            directors = ld["director"]
            if isinstance(directors, list):
                names = [d.get("name", str(d)) if isinstance(d, dict) else str(d) for d in directors]
                context_parts.append(f"JSON-LD director: {', '.join(names)}")
            elif isinstance(directors, dict):
                context_parts.append(f"JSON-LD director: {directors.get('name', directors)}")

    structured_context = "\n".join(context_parts)

    prompt = f"""Analyze this webpage and extract metadata. Return ONLY valid JSON with no additional text.

Structured data from page:
{structured_context}

Page text content:
{page_text[:5000]}

Extract and return JSON with these fields:
- "title": The main title of the content (article title, book title, movie title, etc.)
- "author": The author/creator/director name, or null if not found
- "content_type": One of: "article", "book", "movie", "tv_show", "podcast", "youtube", "research_paper", "pdf", "github", "substack", "medium", "unknown"

Return ONLY the JSON object, no markdown, no explanation:"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response
    response_text = response.content[0].text.strip()

    # Try to extract JSON from response
    try:
        # Handle case where response might have markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        data = json.loads(response_text)

        return ExtractedMetadata(
            title=data.get("title", "Unknown"),
            author=data.get("author"),
            content_type=data.get("content_type", "unknown"),
            image_url=structured.og_image,
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response_text}")


def main():
    """CLI interface for LLM extraction."""
    if len(sys.argv) < 3:
        print("Usage: python -m consumed.llm_extract <url> <html_file>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    html_file = sys.argv[2]

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    try:
        metadata = extract_with_llm(html, url)
        result = {
            "title": metadata.title,
            "author": metadata.author,
            "content_type": metadata.content_type,
        }
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
