"""Full-text article extractor using readability-style extraction."""

import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Tags that typically contain article content
_CONTENT_TAGS = {"article", "main", "section"}
_CONTENT_CLASSES = re.compile(
    r"article|post|entry|content|body|text|story|main", re.IGNORECASE
)
_NEGATIVE_CLASSES = re.compile(
    r"comment|sidebar|footer|header|nav|menu|widget|ad|social|share|related|promo",
    re.IGNORECASE,
)
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"}


@dataclass
class ExtractionResult:
    """Container for full-text extraction results."""

    text: str
    success: bool
    word_count: int = 0
    error: str | None = None


def _score_element(element) -> float:
    """Score a DOM element for likelihood of being article content."""
    score = 0.0

    tag = element.name or ""
    if tag in _CONTENT_TAGS:
        score += 30

    cls = " ".join(element.get("class", []))
    el_id = element.get("id", "")
    combined = f"{cls} {el_id}"

    if _CONTENT_CLASSES.search(combined):
        score += 25
    if _NEGATIVE_CLASSES.search(combined):
        score -= 25

    # Reward elements with lots of paragraph text
    paragraphs = element.find_all("p", recursive=True)
    text_len = sum(len(p.get_text(strip=True)) for p in paragraphs)
    score += min(text_len / 50, 50)  # Cap bonus at 50

    return score


def _clean_text(text: str) -> str:
    """Normalize whitespace in extracted text."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n\n".join(lines)


def extract_article_text(html: str) -> str:
    """Extract article body text from HTML using readability-style heuristics.

    Returns cleaned plain text of the article body.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts, styles, comments, nav, footer
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Score all candidate containers
    candidates = soup.find_all(["div", "article", "main", "section"])
    if not candidates:
        # Fallback: use body
        body = soup.find("body")
        if body:
            return _clean_text(body.get_text(separator="\n", strip=True))
        return ""

    best = max(candidates, key=_score_element)

    # Extract text from paragraphs and block elements within the best candidate
    blocks = best.find_all(_BLOCK_TAGS)
    if blocks:
        text_parts = [b.get_text(strip=True) for b in blocks if b.get_text(strip=True)]
        return _clean_text("\n".join(text_parts))

    # Fallback: get all text from the best candidate
    return _clean_text(best.get_text(separator="\n", strip=True))


async def fetch_full_text(url: str, timeout: float = 15.0) -> ExtractionResult:
    """Fetch a URL and extract the full article text.

    Args:
        url: The article URL to fetch.
        timeout: HTTP request timeout in seconds.

    Returns:
        ExtractionResult with the extracted text.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": ("Mozilla/5.0 (compatible; Pheme/0.2; news digest)"),
                },
            )
            resp.raise_for_status()

        text = extract_article_text(resp.text)
        word_count = len(text.split())

        if word_count < 20:
            return ExtractionResult(
                text=text,
                success=False,
                word_count=word_count,
                error="Extracted text too short",
            )

        return ExtractionResult(
            text=text,
            success=True,
            word_count=word_count,
        )

    except Exception as exc:
        logger.debug("Full-text extraction failed for %s: %s", url, exc)
        return ExtractionResult(
            text="",
            success=False,
            error=str(exc),
        )
