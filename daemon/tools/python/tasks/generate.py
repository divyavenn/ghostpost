"""
Module 2: Generate post content from entry data.

Creates formatted content suitable for Substack Notes.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

import anthropic


@dataclass
class LogEntry:
    """Entry data passed from Rust."""
    url: str
    title: str
    authors: Optional[str]
    date: str


@dataclass
class Post:
    """A generated post ready for publishing."""
    content: str
    url: str
    title: str


@dataclass
class Recommendation:
    """An LLM-generated recommendation for sharing content."""
    content: str
    url: str
    title: str
    excerpt: Optional[str]


def create_recommendation(
    url: str,
    title: Optional[str] = None,
    authors: Optional[str] = None,
    content_type: Optional[str] = None,
    excerpt: Optional[str] = None,
    scraped_content: Optional[str] = None,
    notes: Optional[str] = None,
) -> Recommendation:

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Build context for the LLM
    context_parts = [f"URL: {url}"]

    if title:
        context_parts.insert(0, f"Title: {title}")

    if authors:
        context_parts.append(f"Author(s): {authors}")

    if content_type:
        context_parts.append(f"Type: {content_type}")
        
    if excerpt:
        context_parts.append(f"Excerpt: {excerpt}")

    if notes:
        context_parts.append(f"Reader's notes: {notes}")

    if scraped_content:
        preview = scraped_content[:15000]
        if len(scraped_content) > 15000:
            preview += "\n[...truncated]"
        context_parts.append(f"Content Preview:\n{preview}")

    context = "\n".join(context_parts)


    prompt = f""" You are a writer known for their great taste and high-signal curation of books, essays, movies, and more.
        
        Explicity state that you liked it and say why. Incorporate the reader's notes, 
        preserving as much of their original phrasing as possible.
        Explain the tangible benefit by directly addressing who would enjoy this. 
        deliver the sentiment in the fewest possible words (1-3 sentences). avoid cliche. be informal. no emdashes or colons
        When including a quoted excerpt or bullet list, separate it from the prose with a blank line.
        
        Do NOT include the URL in your recommendation. The URL will be added separately.
        if it's a book or a movie, make sure to include the title.

        Example 1:

        URL: https://www.henrikkarlsson.xyz/p/unfolding
        Title: Everything that turned out well in my life followed the same design process
        Authors(s): Henrik Karlsson
        Type: Substack
        Excerpt: "To find a good relationship, you do not start by saying, 
        “I want a relationship that looks like this”—that would be starting in the wrong end, by defining form. 
        Instead you say, “I’m just going to pay attention to what happens when I hang out with various people and 
        iterate toward something that feels alive”—you start from the context."
        Reader's Notes: need to navigate based on larger context instead of fixating on specific visions 
        
        Recommendation:

        "today I was reading Henrik Karlsson's essay on designing your life. made me reflect on the ways 
        i fixate on specific visions instead of gracefully navigating towards what i want within a 
        larger context. Loved this bit especially
        
        "To find a good relationship, you do not start by saying,
        "I want a relationship that looks like this"—that would be starting in the wrong end, by defining form.
        Instead you say, "I'm just going to pay attention to what happens when I hang out with various people and
        iterate toward something that feels alive"—you start from the context."
        
        
        Example 2:

        URL: https://www.amazon.com/User-Friendly-Hidden-Design-Changing/dp/0374279756
        Title: User Friendly: How the Hidden Rules of Design Are Changing the Way We Live, Work, and Play
        Authors(s): Cliff Kuang, Robert Fabricant 
        Type: Book
        
        
        Recommendation:

        "i've been recommending this book to everyone, one of the most insight-dense, 
        well written books on design I've read in a while.
        
        User Friendly: How the Hidden Rules of Design Are Changing the Way We Live, Work, and Play
        
        
        Example 3:
        
        URL: https://guzey.com/personal/why-have-a-blog/
        Excerpt: Academics gain prestige by publishing novel stuff.
        This gives them a warped perspective on what is valuable.
        You can't publish a paper that would summarize five other papers and argue that
        these papers are undervalued in a top journal but in the real world the value of
        doing that might be very high. The mechanisms of discovery are broken in academia.
        Title: Why You Should Start a Blog Right Now
        Author: Alexey Guzey
        Reader's Notes: not everything you write has to be original to be useful. curation and fresh framing 
        Type: article

        Recommendation:
        
        loved this piece by Alexey Guzey. if you need a push to finally start writing 
        online/making content/thinking in public, you should read it. 
        
        particularly liked this bit about the niche that bloggers can fill that academics kind of can't. 
        not everything u write has to be original to be useful. curation and fresh framings have great value.

        "You can't publish a paper that would summarize five other papers and argue that these papers are undervalued
        in a top journal but in the real world the value of doing that might be very high. The mechanisms of discovery
        are broken in academia."
        
        
        Example 4:
        
        
        URL: https://cybermonk.substack.com/p/the-dark-destination
        Excerpt: I believe each thought is like a melody—each thought seeks resolution. 
        Finding resolution entails the thorough exploration of the thought’s implications and associations, 
        following the threads linking it to identities, memories, sensations, desires, and the future. 
        The existence of intolerable thoughts obstructs this process, replacing comprehension with fear; 
        and since such thoughts are often suppressed from conscious awareness, the fear feels vague and permeating. 
        This is anxiety.
        Title: The dark destination
        Author: ftlsid
        Type: substack
        
        
        Recommendation:
        
        ftlsid wrote something on anxiety I really liked: how anxiety often feels shapeless but inescapable


        "I believe each thought is like a melody—each thought seeks resolution. 
        Finding resolution entails the thorough exploration of the thought's implications and associations, 
        following the threads linking it to identities, memories, sensations, desires, and the future. 
        The existence of intolerable thoughts obstructs this process, replacing comprehension with fear; 
        and since such thoughts are often suppressed from conscious awareness, the fear feels vague and permeating. 
        This is anxiety."

        anxiety is not an irrational thought, it's a thought you won't let yourself finish thinking.
        
        
        Example 5:
        
        
        URL: https://sharif.io/solving-hard-problems
        Title: How to Solve Hard Problems
        Author: Sharif Shameem
        Type: article
        Reader's Notes: strategic decomposition, finding analogies, knowing when to step away.
        
        Recommendation:
        
        if you're banging your head against a problem, read this essay by Sharif

        the core idea is that solving hard problems is less about raw brainpower and more about
        
        - strategic decomposition
        - finding analogies
        - working backwards from the solution
        - knowing when to step away.
        
        
        URL: https://registerspill.thorstenball.com/p/they-all-use-it
        Title: They All Use It
        Author: Thorsten Ball
        Type: substack
        Reader's Notes: I used to think AI tools were mostly toys, feels like hubris

        Recommendation:

        at one point i tried AI tools, decided they were mostly toys, and moved on. 
        wish i'd read this essay by Thorsten Ball earlier:

        he’s not making the case that AI is going to replace you or engaging in AGI cultism, but some of the best 
        engineers alive are using these tools daily and finding them valuable. feels like hubris not to explore.
        
        
        Now write a recommendation for this:

        {context}
        """


    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text.strip()

    # Strip the URL from LLM output if it included one — URL is returned separately
    content = content.replace(url, "").strip()
    # Clean up multiple trailing newlines left behind
    import re
    content = re.sub(r"\n{3,}", "\n\n", content)

    return Recommendation(
        content=content,
        url=url,
        title=title or url,  # Use URL as fallback title
        excerpt=excerpt,
    )


def generate_post(
    entry: LogEntry,
    template: Optional[str] = None,
    include_quote: Optional[str] = None,
    include_thoughts: Optional[str] = None,
) -> Post:
    """
    Generate a post from an entry.

    Args:
        entry: The LogEntry with title, url, authors
        template: Custom template (use {title}, {url}, {authors}, {quote}, {thoughts})
        include_quote: Optional quote from the content
        include_thoughts: Optional personal commentary

    Returns:
        Post ready for publishing
    """
    if template:
        content = template.format(
            title=entry.title,
            url=entry.url,
            authors=entry.authors or "",
            quote=include_quote or "",
            thoughts=include_thoughts or "",
        )
    else:
        # Default template
        lines = []

        # Title and link
        lines.append(f"Reading: {entry.title}")
        lines.append(f"{entry.url}")

        # Author if available
        if entry.authors:
            lines.append(f"by {entry.authors}")

        lines.append("")

        # Quote if provided
        if include_quote:
            lines.append(f'"{include_quote}"')
            lines.append("")

        # Thoughts if provided
        if include_thoughts:
            lines.append(include_thoughts)

        content = "\n".join(lines)

    return Post(
        content=content.strip(),
        url=entry.url,
        title=entry.title,
    )


def main():
    """CLI interface for recommendation generation.

    Called by Rust daemon with metadata already extracted.

    Usage:
        python -m consumed.generate '<json>'     # Single item with metadata
        python -m consumed.generate --test       # Run test data (fetches metadata)

    JSON input (from daemon):
        - url (required)
        - title (from Rust metadata extraction)
        - author (from Rust metadata extraction)
        - content_type (from Rust metadata extraction)
        - excerpt (optional) - selected text from the page
    """
    import sys

    # Test data for manual testing
    test_bookmarks = [
        {
            "url": "https://harpers.org/archive/2026/03/childs-play-sam-kriss-ai-startup-roy-lee/",
            "excerpt": """It did not seem like a good idea to me that some of the richest people in 
            the world were no longer rewarding people for having any particular skills, 
            but simply for having agency, when agency essentially meant whatever it was that was afflicting Roy Lee.""",
        },
        {
            "url": "https://cybermonk.substack.com/p/the-ability-to-choose",
            "excerpt": """during that time my life felt like something that was happening to me. 
            I experienced pervasive confusion; I had personally made every major decision that shaped my 
            conditions, but nonetheless I felt viscerally like the life that emerged from those decisions was not mine.
            """,
        },
        {"url": "https://en.wikipedia.org/wiki/Wuthering_Heights"},
        {"url": "https://www.imdb.com/title/tt1592281/"},
        {"url" : "https://news.lettersofnote.com/p/i-love-my-wife-my-wife-is-dead"},
        {"url" : "https://en.wikipedia.org/wiki/The_Secret_Garden"}
    ]

    # Test mode - mirrors the actual bookmark pipeline
    if len(sys.argv) < 2:
        import httpx
        from llm_extract import extract_with_llm
        import sys
        from pathlib import Path
        scrapers_dir = Path(__file__).resolve().parents[2] / "scrapers"
        if str(scrapers_dir) not in sys.path:
            sys.path.append(str(scrapers_dir))
        from scrape import scrape

        for b in test_bookmarks:
            url = b["url"]
            excerpt = b.get("excerpt")

            print(f"\n{'='*60}")
            print(f"URL: {url}")
            if excerpt:
                print(f"Excerpt: {excerpt[:100]}...")

            try:
                # Step 1: Extract metadata (simulating what Rust does)
                print("Extracting metadata...")
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                response = httpx.get(url, follow_redirects=True, timeout=30.0, headers=headers)
                response.raise_for_status()
                metadata = extract_with_llm(response.text, url)
                print(f"  Title: {metadata.title}")
                print(f"  Author: {metadata.author}")
                print(f"  Type: {metadata.content_type}")

                # Step 2: Scrape content (same scraper the daemon uses)
                print("Scraping content...")
                scrape_result = scrape(url, metadata.content_type)
                scraped_markdown = scrape_result.get("markdown")
                if scraped_markdown:
                    print(f"  Scraped {len(scraped_markdown)} chars")
                else:
                    print("  No scraper for this content type")

                # Step 3: Generate recommendation with full context
                print("Generating recommendation...")
                recommendation = create_recommendation(
                    url=url,
                    title=metadata.title,
                    authors=metadata.author,
                    content_type=metadata.content_type,
                    excerpt=excerpt,
                    scraped_content=scraped_markdown,
                )

                print("\n--- GENERATED POST ---")
                print(recommendation.content)
                print("--- END ---\n")

            except Exception as e:
                print(f"Error: {e}")

        return

    # Normal mode - receive JSON from Rust daemon
    try:
        input_data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    url = input_data.get("url")
    if not url:
        print(json.dumps({"error": "Missing required field: url"}))
        sys.exit(1)

    try:
        recommendation = create_recommendation(
            url=url,
            title=input_data.get("title"),
            authors=input_data.get("author"),  # Rust uses "author" not "authors"
            content_type=input_data.get("content_type"),
            excerpt=input_data.get("excerpt"),
            scraped_content=input_data.get("scraped_content"),
            notes=input_data.get("notes"),
        )

        result = {
            "content": recommendation.content,
            "url": recommendation.url,
            "title": recommendation.title,
            "author": input_data.get("author"),
            "content_type": input_data.get("content_type"),
            "excerpt": recommendation.excerpt,
            "image_url": input_data.get("image_url"),
        }
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()


