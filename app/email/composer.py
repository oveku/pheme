"""Digest email composer - renders HTML and plain-text from Digest model."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.models import Digest

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )


def compose_digest_html(digest: Digest) -> str:
    """Render the digest as an HTML email body."""
    env = _get_jinja_env()
    template = env.get_template("digest.html")
    return template.render(
        digest=digest,
        date=digest.generated_at.strftime("%A, %B %d, %Y"),
        article_count=digest.article_count,
        source_count=digest.source_count,
    )


def compose_digest_plain(digest: Digest) -> str:
    """Render the digest as plain text (fallback)."""
    lines: list[str] = []
    date_str = digest.generated_at.strftime("%A, %B %d, %Y")
    lines.append(f"Pheme Daily Digest - {date_str}")
    lines.append(
        f"{digest.article_count} articles from {digest.source_count} sources"
    )
    lines.append("=" * 50)

    if digest.summary:
        lines.append("")
        lines.append(digest.summary)

    # Topic sections (Phase 2)
    if digest.topic_sections:
        for section in digest.topic_sections:
            if not section.entries:
                continue
            lines.append("")
            lines.append(
                f"--- {section.topic_name} ({len(section.entries)}) ---"
            )
            for entry in section.entries:
                lines.append(f"  {entry.article.title}")
                lines.append(f"  {entry.article.url}")
                lines.append(f"  {entry.summary}")
                lines.append("")
    elif digest.entries:
        lines.append("")
        for entry in digest.entries:
            lines.append(f"  {entry.article.title}")
            lines.append(f"  {entry.article.url}")
            if entry.summary:
                lines.append(f"  {entry.summary}")
            lines.append("")
    else:
        lines.append("")
        lines.append("No articles were fetched today.")

    lines.append("-" * 50)
    lines.append("Pheme - Your Daily News Digest")
    return "\n".join(lines)
