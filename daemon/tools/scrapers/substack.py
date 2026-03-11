"""
Takes a list of Substack post URLs, downloads each
article, and converts it into a Markdown file. The generated Markdown mirrors
the page structure: title and subtitle metadata, hero images (with original
sources), headings, emphasis, block quotes, lists, and closing resource links.

Substack UI clutter such as subscribe prompts or "read more" footers is
removed. Mojibake artefacts (e.g. ``youâre``) are normalised back into their
intended smart punctuation.

Requirements:
    - requests
    - beautifulsoup4

"""

from __future__ import annotations

import json
from datetime import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import textwrap

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Update this list with the Substack posts you want to export.
SUBSTACK_URLS = [
    "https://divyavenn.substack.com/p/how-to-become-exceptional",
    # Add more URLs here.
]

# Where to store the generated Markdown files.
OUTPUT_DIR = Path("substack_exports")

# Persistent storage for the Substack session cookie. The file is created on
# demand the first time the exporter runs (CLI mode).
SESSION_FILE = Path("substack_session.json")

# Lazily populated cache of the user's session cookie so imports remain
# side-effect free (useful for API deployments).
_SESSION_COOKIES: dict[str, str] | None = None

REQUEST_HEADERS = {
    # Mirror browser headers so Substack serves subscriber-only content.
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9," 
        "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://divyavenn.substack.com/?utm_campaign=profile_chips",
    "Sec-GPC": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Helpful when Substack tweaks markup. Toggle on to capture the raw HTML
# returned for each URL so we can inspect the structure locally.
DEBUG_SAVE_RESPONSES = True


def load_session_cookies() -> dict[str, str]:
    """Retrieve the Substack session cookie, prompting the user if needed."""

    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
        except json.JSONDecodeError as exc:
            print(f"Existing {SESSION_FILE} is not valid JSON ({exc}).")
        else:
            cookies = data.get("cookies") if isinstance(data, dict) else None
            if isinstance(cookies, dict) and "substack.sid" in cookies:
                value = str(cookies["substack.sid"]).strip()
                if value:
                    return {"substack.sid": value}
                print(f"Existing {SESSION_FILE} contains an empty 'substack.sid' value.")
            print(f"Existing {SESSION_FILE} is missing the 'substack.sid' cookie.")

    print(
        textwrap.dedent(
            """
            Substack session cookie required.

            1. Log in to Substack in your browser.
            2. Open DevTools → Console.
            3. Paste the helper snippet from docs/get_substack_cookie.md and press Enter.
            4. Paste the copied cookie value below (leave it URL-encoded).
            """
        ).strip()
    )

    while True:
        try:
            value = input("substack.sid cookie value: ").strip()
        except EOFError:
            raise SystemExit("No cookie provided; aborting.")

        if not value:
            print("Cookie cannot be empty. Please paste the value shown in DevTools.")
            continue

        if " " in value:
            print("Cookie contains spaces. Make sure you copied the exact value from the console.")
            continue

        if not value.startswith("s%3A"):
            confirm = input(
                "Value does not look URL-encoded (expected to start with 's%3A'). Use anyway? [y/N]: "
            ).strip().lower()
            if confirm not in {"y", "yes"}:
                print("Let's try that again.")
                continue

        break

    cookies = {"substack.sid": value}
    payload = {
        "cookies": cookies,
        "updated": datetime.utcnow().isoformat() + "Z",
    }
    SESSION_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved cookie to {SESSION_FILE}. Keep this file private.")
    return cookies



def ensure_session_cookies() -> dict[str, str]:
    """Return cached session cookies, prompting the user if necessary."""

    global _SESSION_COOKIES
    if _SESSION_COOKIES is None:
        _SESSION_COOKIES = load_session_cookies()
    return _SESSION_COOKIES
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def fetch_html(url: str, cookies: Optional[dict[str, str]] = None) -> str:
    """Download the HTML for *url* and return the text."""

    cookie_jar = cookies if cookies is not None else ensure_session_cookies()

    response = requests.get(
        url,
        timeout=30,
        headers=REQUEST_HEADERS,
        cookies=cookie_jar if cookie_jar else None,
    )
    response.raise_for_status()
    html = response.text

    if DEBUG_SAVE_RESPONSES:
        debug_dir = OUTPUT_DIR / "_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(url.replace("https://", ""))[:80]
        (debug_dir / f"{slug or 'response'}.html").write_text(html, encoding="utf-8")

    return html


def fix_mojibake(text: str) -> str:
    """Fix common UTF-8 mojibake sequences that appear in saved Substack HTML."""

    if not text:
        return ""

    result: List[str] = []
    buffer = bytearray()

    for ch in text:
        code = ord(ch)
        if code <= 0xFF:
            buffer.append(code)
        else:
            if buffer:
                result.append(_decode_buffer(buffer))
                buffer.clear()
            result.append(ch)

    if buffer:
        result.append(_decode_buffer(buffer))

    return "".join(result)


def _decode_buffer(buffer: bytearray) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return buffer.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort — should not happen, but avoids hard failure.
    return buffer.decode("latin-1", errors="replace")


def clean_text(text: Optional[str]) -> str:
    """Normalise spacing and mojibake artefacts."""

    if text is None:
        return ""
    text = text.replace("\xa0", " ")
    text = fix_mojibake(text)
    return text


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "substack-article"


def derive_filename(url: str, title: str) -> str:
    """Build a filename from the URL slug (fallback to title if needed)."""

    slug = url.rstrip("/").split("/")[-1]
    if not slug or slug.startswith("?ref="):
        slug = slugify(title)
    return f"{slug}.md"


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_img_src(tag: Tag) -> tuple[str, str, str]:
    src = tag.get("src", "")
    attrs = tag.get("data-attrs")
    if attrs:
        try:
            data = json.loads(attrs)
            if isinstance(data, dict) and data.get("src"):
                src = data["src"]
        except json.JSONDecodeError:
            pass
    alt = clean_text(tag.get("alt", "").strip())
    title = clean_text(tag.get("title", "").strip())
    return src, alt, title


def join_fragments(fragments: Iterable[str]) -> str:
    """Join inline fragments while ensuring spacing stays readable."""

    out: List[str] = []
    for frag in fragments:
        frag = frag or ""
        if not frag:
            continue
        if out and needs_space(out[-1], frag):
            out.append(" ")
        out.append(frag)
    return "".join(out)


def needs_space(prev: str, nxt: str) -> bool:
    if not prev or not nxt:
        return False
    if prev[-1].isspace() or nxt[0].isspace():
        return False
    if prev[-1] in "([{":
        return False
    if nxt[0] in ")]},.:;!?/\\\"“”’*":
        return False
    return True


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


@dataclass
class RenderState:
    blockquote_level: int = 0
    list_stack: List[dict] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.list_stack is None:
            self.list_stack = []


def render_article_metadata(article: Tag) -> dict:
    title = clean_text(article.find("h1").get_text(strip=True)) if article.find("h1") else ""
    subtitle = clean_text(article.find("h3").get_text(strip=True)) if article.find("h3") else ""

    author_text = ""
    author_href = ""
    for anchor in article.find_all("a"):
        text = clean_text(anchor.get_text(strip=True))
        if text:
            author_text = text
            author_href = anchor.get("href", "")
            break

    date_text = ""
    badge_text = ""
    for div in article.find_all("div"):
        class_attr = div.get("class") or []
        class_text = " ".join(class_attr)
        if "meta" not in class_text:
            continue
        text = clean_text(div.get_text(strip=True))
        if not text:
            continue
        if not date_text and any(month in text for month in MONTH_NAMES):
            date_text = text
            continue
        if not badge_text and "Paid" in text:
            badge_text = text

    return {
        "title": title,
        "subtitle": subtitle,
        "author_text": author_text,
        "author_href": author_href,
        "date_text": date_text,
        "badge_text": badge_text,
    }


def render_article_body(article: Tag) -> List[str]:
    body = article.find("div", class_="body markup")
    if body is None:
        raise ValueError("Could not locate Substack article body")

    state = RenderState()
    lines: List[str] = []

    for child in body.children:
        block = render_node(child, state)
        if not block:
            continue
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(block)

    while lines and not lines[-1].strip():
        lines.pop()

    filtered: List[str] = []
    for line in lines:
        trimmed = line.strip().lower()
        if trimmed in {"subscribe", "subscribed"}:
            continue
        if trimmed.startswith("[read more]("):
            continue
        filtered.append(line)

    return filtered


def render_node(node, state: RenderState) -> List[str]:
    if isinstance(node, NavigableString):
        text = clean_text(str(node))
        return [text] if text.strip() else []

    if not isinstance(node, Tag):
        return []

    name = node.name.lower()

    if name == "p":
        return render_paragraph(node, state)
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return render_heading(node, state)
    if name == "blockquote":
        return render_blockquote(node, state)
    if name == "ul":
        return render_list(node, state, ordered=False)
    if name == "ol":
        return render_list(node, state, ordered=True)
    if name == "li":
        return render_list_item(node, state)
    if name == "pre":
        return render_pre(node, state)
    if name == "hr":
        return apply_blockquote(["---"], state)
    if name == "figure":
        return render_figure(node, state)
    if name in {"div", "section", "article"}:
        lines: List[str] = []
        for child in node.children:
            lines.extend(render_node(child, state))
        return lines
    if name == "table":
        return render_table(node, state)

    inline_text = render_inline(node)
    if inline_text.strip():
        return apply_blockquote([inline_text], state)
    return []


def apply_blockquote(lines: List[str], state: RenderState) -> List[str]:
    if state.blockquote_level <= 0:
        return lines
    prefix = "> " * state.blockquote_level
    return [prefix + line if line else prefix.strip() for line in lines]


def render_paragraph(tag: Tag, state: RenderState) -> List[str]:
    text = render_inline(tag).strip()
    if not text:
        return []
    return apply_blockquote([text], state)


def render_heading(tag: Tag, state: RenderState) -> List[str]:
    level = int(tag.name[1])
    text = render_inline(tag).strip()
    if not text:
        return []
    heading = "#" * level + " " + text
    return apply_blockquote([heading], state)


def render_blockquote(tag: Tag, state: RenderState) -> List[str]:
    state.blockquote_level += 1
    lines: List[str] = []
    for child in tag.children:
        lines.extend(render_node(child, state))
    state.blockquote_level -= 1
    return lines


def render_list(tag: Tag, state: RenderState, ordered: bool) -> List[str]:
    state.list_stack.append({"ordered": ordered, "index": 0})
    lines: List[str] = []
    for child in tag.children:
        if isinstance(child, Tag) and child.name.lower() == "li":
            lines.extend(render_list_item(child, state))
    state.list_stack.pop()
    return lines


def render_list_item(tag: Tag, state: RenderState) -> List[str]:
    stack_entry = state.list_stack[-1]
    stack_entry["index"] += 1

    marker = f"{stack_entry['index']}." if stack_entry["ordered"] else "-"
    indent = "  " * (len(state.list_stack) - 1)
    prefix = indent + marker + " "
    continuation = indent + " " * (len(marker) + 1)

    parts: List[str] = []
    buffer: List[str] = []

    for child in tag.children:
        if isinstance(child, NavigableString):
            buffer.append(clean_text(str(child)))
            continue

        if isinstance(child, Tag) and child.name.lower() in {"p", "ul", "ol", "blockquote", "div", "section", "pre"}:
            text = join_fragments(buffer).strip()
            if text:
                parts.append(text)
            buffer.clear()
            parts.extend(render_node(child, state))
        else:
            buffer.append(render_inline(child))

    text = join_fragments(buffer).strip()
    if text:
        parts.insert(0, text)

    if not parts:
        return []

    rendered: List[str] = []
    first = True
    for line in parts:
        if not line:
            continue
        if first:
            rendered.append(prefix + line)
            first = False
        else:
            rendered.append(continuation + line)

    return apply_blockquote(rendered, state)


def render_pre(tag: Tag, state: RenderState) -> List[str]:
    code_text = clean_text(tag.get_text())
    code_text = code_text.rstrip("\n")
    block = ["```", code_text, "```"]
    return apply_blockquote(block, state)


def render_figure(tag: Tag, state: RenderState) -> List[str]:
    lines: List[str] = []
    img = tag.find("img")
    if img:
        src, alt, title = parse_img_src(img)
        title_part = f' "{title}"' if title else ""
        lines.append(f"![{alt}]({src}{title_part})")
    caption_tag = tag.find("figcaption")
    if caption_tag:
        caption = render_inline(caption_tag).strip()
        if caption:
            lines.append(f"*{caption}*")
    return apply_blockquote(lines, state)


def render_table(tag: Tag, state: RenderState) -> List[str]:
    rows: List[str] = []
    header_cols = 0

    for tr in tag.find_all("tr"):
        cells: List[str] = []
        header_row = False
        for cell in tr.find_all(["th", "td"], recursive=False):
            cells.append(render_inline(cell).strip())
            header_row = header_row or cell.name.lower() == "th"
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
            if header_row:
                header_cols = max(header_cols, len(cells))

    if not rows:
        return []

    output: List[str] = [rows[0]]
    if header_cols:
        output.append("| " + " | ".join(["---"] * header_cols) + " |")
        output.extend(rows[1:])
    else:
        output.extend(rows[1:])

    return apply_blockquote(output, state)


def render_inline(tag: Tag) -> str:
    if isinstance(tag, NavigableString):
        return clean_text(str(tag))

    name = tag.name.lower()

    if name in {"strong", "b"}:
        inner = render_inline_children(tag).strip()
        return f"**{inner}**" if inner else ""
    if name in {"em", "i"}:
        inner = render_inline_children(tag).strip()
        return f"_{inner}_" if inner else ""
    if name == "code":
        inner = render_inline_children(tag)
        inner = inner.replace("`", "\\`")
        return f"`{inner}`" if inner else ""
    if name == "a":
        text = render_inline_children(tag).strip()
        href = tag.get("href", "").strip()
        return f"[{text}]({href})" if text and href else text
    if name == "br":
        return "  \n"
    if name == "img":
        src, alt, title = parse_img_src(tag)
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({src}{title_part})"
    if name in {"span", "u", "abbr", "cite", "q", "mark", "sup", "sub"}:
        if name == "sup":
            inner = render_inline_children(tag).strip()
            return f"^{{{inner}}}" if inner else ""
        if name == "sub":
            inner = render_inline_children(tag).strip()
            return f"~{{{inner}}}" if inner else ""
        return render_inline_children(tag)

    return render_inline_children(tag)


def render_inline_children(tag: Tag) -> str:
    fragments: List[str] = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            fragments.append(clean_text(str(child)))
        elif isinstance(child, Tag):
            fragments.append(render_inline(child))
    return join_fragments(fragments)


# ---------------------------------------------------------------------------
# Conversion pipeline
# ---------------------------------------------------------------------------


def convert_html_to_markdown(html: str, url: str) -> tuple[str, dict]:
    """Convert a Substack article HTML document to Markdown."""

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    if article is None:
        raise ValueError(f"Could not find article element in {url}")

    metadata = render_article_metadata(article)
    body_lines = render_article_body(article)

    markdown = "\n".join(body_lines).rstrip() + "\n"
    return markdown, metadata


def convert_substack_post(url: str, output_dir: Path) -> Path:
    html = fetch_html(url)
    markdown, metadata = convert_html_to_markdown(html, url)

    output_dir = output_dir.resolve()
    ensure_output_dir(output_dir)

    filename = derive_filename(url, metadata["title"])
    destination = output_dir / filename
    counter = 1
    while destination.exists():
        destination = output_dir / f"{destination.stem}-{counter}{destination.suffix}"
        counter += 1

    destination.write_text(markdown, encoding="utf-8")
    return destination


def main() -> None:
    ensure_output_dir(OUTPUT_DIR)
    for url in SUBSTACK_URLS:
        try:
            output_path = convert_substack_post(url, OUTPUT_DIR)
            print(f"✓ Exported {url} → {output_path}")
        except Exception as exc:  # pragma: no cover - surfaced to user
            print(f"✗ Failed to export {url}: {exc}")


if __name__ == "__main__":
    main()
