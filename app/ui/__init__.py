"""Simple admin UI routes for Pheme."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.database import get_db, get_sources, get_topics, get_digest_logs

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared HTML helpers
# ---------------------------------------------------------------------------

_HEAD = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pheme Admin - {title}</title>
    <link rel="icon" type="image/png" href="/static/pheme-icon.png">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #e0e0e0;
            line-height: 1.6; padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        nav {{ background: #16213e; padding: 12px 20px; border-radius: 8px; margin-bottom: 24px; display: flex; gap: 16px; align-items: center; }}
        nav a {{ color: #4fc3f7; text-decoration: none; font-weight: 500; }}
        nav a:hover {{ text-decoration: underline; }}
        nav .brand {{ font-size: 18px; font-weight: bold; color: #fff; margin-right: auto; }}
        h1 {{ color: #4fc3f7; margin-bottom: 16px; font-size: 22px; }}
        .card {{ background: #16213e; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
        .card h3 {{ color: #4fc3f7; margin-bottom: 4px; }}
        .card .meta {{ color: #888; font-size: 13px; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
        .badge-on {{ background: #2e7d32; color: #c8e6c9; }}
        .badge-off {{ background: #c62828; color: #ffcdd2; }}
        .badge-type {{ background: #1565c0; color: #bbdefb; }}
        .badge-topic {{ background: #6a1b9a; color: #e1bee7; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
        th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #2a2a4a; }}
        th {{ color: #4fc3f7; font-size: 13px; text-transform: uppercase; }}
        form {{ background: #16213e; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 4px; color: #aaa; font-size: 13px; }}
        input, select, textarea {{
            width: 100%; padding: 8px 12px; border: 1px solid #333;
            border-radius: 6px; background: #0f3460; color: #e0e0e0;
            font-size: 14px; margin-bottom: 12px;
        }}
        textarea {{ min-height: 80px; resize: vertical; }}
        button {{
            background: #4fc3f7; color: #1a1a2e; border: none; padding: 10px 20px;
            border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer;
        }}
        button:hover {{ background: #29b6f6; }}
        .btn-danger {{ background: #e53935; color: #fff; }}
        .btn-danger:hover {{ background: #c62828; }}
        .btn-sm {{ padding: 4px 10px; font-size: 12px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .msg {{ padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }}
        .msg-ok {{ background: #1b5e20; color: #c8e6c9; }}
        .msg-err {{ background: #b71c1c; color: #ffcdd2; }}
        .keywords {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }}
        .kw {{ background: #0f3460; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
    </style>
</head>
"""


def _nav() -> str:
    return """
    <nav>
        <img src="/static/pheme-icon.png" alt="Pheme" style="width:28px;height:28px;border-radius:6px;">
        <span class="brand">Pheme</span>
        <a href="/admin">Dashboard</a>
        <a href="/admin/sources">Sources</a>
        <a href="/admin/topics">Topics</a>
        <a href="/admin/digest">Digest</a>
    </nav>
    """


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Admin dashboard overview."""
    db = await get_db()
    sources = await get_sources(db)
    topics = await get_topics(db)
    logs = await get_digest_logs(db, limit=5)

    enabled_sources = sum(1 for s in sources if s.enabled)
    enabled_topics = sum(1 for t in topics if t.enabled)

    log_rows = ""
    for log in logs:
        log_rows += f"""
        <tr>
            <td>{log.sent_at.strftime('%Y-%m-%d %H:%M')}</td>
            <td>{log.source_count}</td>
            <td>{log.article_count}</td>
            <td><span class="badge {'badge-on' if log.status == 'sent' else 'badge-off'}">{log.status}</span></td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en">
    {_HEAD.format(title="Dashboard")}
    <body><div class="container">
    {_nav()}
    <h1>Dashboard</h1>
    <div class="grid">
        <div class="card">
            <h3>{len(sources)}</h3>
            <div class="meta">Sources ({enabled_sources} enabled)</div>
        </div>
        <div class="card">
            <h3>{len(topics)}</h3>
            <div class="meta">Topics ({enabled_topics} enabled)</div>
        </div>
    </div>
    <h1>Recent Digests</h1>
    <table>
        <tr><th>Date</th><th>Sources</th><th>Articles</th><th>Status</th></tr>
        {log_rows if log_rows else '<tr><td colspan="4">No digests sent yet.</td></tr>'}
    </table>
    </div></body></html>"""


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@router.get("/admin/sources", response_class=HTMLResponse)
async def admin_sources():
    """List and manage sources."""
    db = await get_db()
    sources = await get_sources(db)
    topics = await get_topics(db)

    topic_map = {t.id: t.name for t in topics}
    topic_options = "".join(f'<option value="{t.id}">{t.name}</option>' for t in topics)

    source_cards = ""
    for s in sources:
        topic_badges = ""
        for tid in s.topic_ids:
            tname = topic_map.get(tid, f"#{tid}")
            topic_badges += f'<span class="badge badge-topic">{tname}</span> '

        source_cards += f"""
        <div class="card">
            <h3>{s.name}
                <span class="badge badge-type">{s.type.value}</span>
                <span class="badge {'badge-on' if s.enabled else 'badge-off'}">{'on' if s.enabled else 'off'}</span>
            </h3>
            <div class="meta">{s.url}</div>
            <div class="meta">Category: {s.category} | Last fetched: {s.last_fetched or 'never'}</div>
            <div class="keywords">{topic_badges}</div>
            <form method="post" action="/admin/sources/{s.id}/delete" style="margin-top:8px;background:transparent;padding:0;">
                <button type="submit" class="btn-danger btn-sm">Delete</button>
            </form>
        </div>"""

    return f"""<!DOCTYPE html><html lang="en">
    {_HEAD.format(title="Sources")}
    <body><div class="container">
    {_nav()}
    <h1>Add Source</h1>
    <form method="post" action="/admin/sources/add">
        <div class="grid">
            <div><label>Name</label><input name="name" required></div>
            <div><label>Type</label>
                <select name="type">
                    <option value="rss">RSS</option>
                    <option value="reddit">Reddit</option>
                    <option value="web">Web</option>
                </select>
            </div>
        </div>
        <label>URL</label><input name="url" required placeholder="https://... or r/subreddit">
        <div class="grid">
            <div><label>Category</label><input name="category" value="general"></div>
            <div><label>Topics</label>
                <select name="topic_ids" multiple style="min-height:60px;">
                    {topic_options}
                </select>
            </div>
        </div>
        <button type="submit">Add Source</button>
    </form>
    <h1>Sources ({len(sources)})</h1>
    {source_cards if source_cards else '<div class="card"><p>No sources configured yet.</p></div>'}
    </div></body></html>"""


@router.post("/admin/sources/add", response_class=HTMLResponse)
async def admin_add_source(request: Request):
    """Handle source creation from form."""
    from app.database import create_source
    from app.models import SourceCreate, SourceType

    form = await request.form()
    topic_ids = [int(x) for x in form.getlist("topic_ids")]

    try:
        db = await get_db()
        await create_source(
            db,
            SourceCreate(
                name=form["name"],
                type=SourceType(form["type"]),
                url=form["url"],
                category=form.get("category", "general"),
                topic_ids=topic_ids,
            ),
        )
        return _redirect("/admin/sources")
    except Exception as exc:
        return _error_page(f"Failed to add source: {exc}")


@router.post("/admin/sources/{source_id}/delete", response_class=HTMLResponse)
async def admin_delete_source(source_id: int):
    """Handle source deletion."""
    from app.database import delete_source

    db = await get_db()
    await delete_source(db, source_id)
    return _redirect("/admin/sources")


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


@router.get("/admin/topics", response_class=HTMLResponse)
async def admin_topics():
    """List and manage topics."""
    db = await get_db()
    topics = await get_topics(db)

    topic_cards = ""
    for t in topics:
        kw_badges = "".join(f'<span class="kw">{kw}</span>' for kw in t.keywords)
        topic_cards += f"""
        <div class="card">
            <h3>{t.name}
                <span class="badge {'badge-on' if t.enabled else 'badge-off'}">{'on' if t.enabled else 'off'}</span>
            </h3>
            <div class="meta">Priority: {t.priority} | Max articles: {t.max_articles}</div>
            <div class="keywords">{kw_badges if kw_badges else '<span class="kw">no keywords</span>'}</div>
            {('<div class="meta" style="margin-top:4px;">Include: ' + ', '.join(t.include_patterns) + '</div>') if t.include_patterns else ''}
            {('<div class="meta">Exclude: ' + ', '.join(t.exclude_patterns) + '</div>') if t.exclude_patterns else ''}
            <form method="post" action="/admin/topics/{t.id}/delete" style="margin-top:8px;background:transparent;padding:0;">
                <button type="submit" class="btn-danger btn-sm">Delete</button>
            </form>
        </div>"""

    return f"""<!DOCTYPE html><html lang="en">
    {_HEAD.format(title="Topics")}
    <body><div class="container">
    {_nav()}
    <h1>Add Topic</h1>
    <form method="post" action="/admin/topics/add">
        <div class="grid">
            <div><label>Name</label><input name="name" required placeholder="e.g. AI & Machine Learning"></div>
            <div><label>Priority (0-100)</label><input name="priority" type="number" value="50" min="0" max="100"></div>
        </div>
        <label>Keywords (comma-separated)</label>
        <input name="keywords" placeholder="AI, machine learning, neural network, LLM, GPT">
        <label>Include patterns (comma-separated regex, optional)</label>
        <input name="include_patterns" placeholder="">
        <label>Exclude patterns (comma-separated regex, optional)</label>
        <input name="exclude_patterns" placeholder="sponsored, advertisement">
        <div class="grid">
            <div><label>Max articles per digest</label><input name="max_articles" type="number" value="10" min="1" max="50"></div>
            <div></div>
        </div>
        <button type="submit">Add Topic</button>
    </form>
    <h1>Topics ({len(topics)})</h1>
    {topic_cards if topic_cards else '<div class="card"><p>No topics configured yet. Add one above.</p></div>'}
    </div></body></html>"""


@router.post("/admin/topics/add", response_class=HTMLResponse)
async def admin_add_topic(request: Request):
    """Handle topic creation from form."""
    from app.database import create_topic
    from app.models import TopicCreate

    form = await request.form()

    def split_csv(val: str) -> list[str]:
        return [x.strip() for x in val.split(",") if x.strip()] if val else []

    try:
        db = await get_db()
        await create_topic(
            db,
            TopicCreate(
                name=form["name"],
                keywords=split_csv(form.get("keywords", "")),
                include_patterns=split_csv(form.get("include_patterns", "")),
                exclude_patterns=split_csv(form.get("exclude_patterns", "")),
                priority=int(form.get("priority", 50)),
                max_articles=int(form.get("max_articles", 10)),
            ),
        )
        return _redirect("/admin/topics")
    except Exception as exc:
        return _error_page(f"Failed to add topic: {exc}")


@router.post("/admin/topics/{topic_id}/delete", response_class=HTMLResponse)
async def admin_delete_topic(topic_id: int):
    """Handle topic deletion."""
    from app.database import delete_topic

    db = await get_db()
    await delete_topic(db, topic_id)
    return _redirect("/admin/topics")


# ---------------------------------------------------------------------------
# Digest preview / trigger
# ---------------------------------------------------------------------------


@router.get("/admin/digest", response_class=HTMLResponse)
async def admin_digest():
    """Digest management page with trigger button and history."""
    db = await get_db()
    logs = await get_digest_logs(db, limit=20)

    log_rows = ""
    for log in logs:
        log_rows += f"""
        <tr>
            <td>{log.sent_at.strftime('%Y-%m-%d %H:%M')}</td>
            <td>{log.recipient}</td>
            <td>{log.source_count}</td>
            <td>{log.article_count}</td>
            <td>{log.entry_count}</td>
            <td><span class="badge {'badge-on' if log.status == 'sent' else 'badge-off'}">{log.status}</span></td>
            <td>{log.error or ''}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en">
    {_HEAD.format(title="Digest")}
    <body><div class="container">
    {_nav()}
    <h1>Digest</h1>
    <div class="card">
        <h3>Trigger Digest</h3>
        <p class="meta" style="margin-bottom:8px;">Manually run the digest pipeline now. This will fetch, summarize, and email.</p>
        <form method="post" action="/admin/digest/trigger" style="background:transparent;padding:0;">
            <button type="submit">Run Digest Now</button>
        </form>
    </div>
    <h1>History</h1>
    <table>
        <tr><th>Date</th><th>Recipient</th><th>Sources</th><th>Articles</th><th>Entries</th><th>Status</th><th>Error</th></tr>
        {log_rows if log_rows else '<tr><td colspan="7">No digests sent yet.</td></tr>'}
    </table>
    </div></body></html>"""


@router.post("/admin/digest/trigger", response_class=HTMLResponse)
async def admin_trigger_digest():
    """Trigger digest from the UI."""
    from app.config import get_settings
    from app.fetchers.factory import FetcherFactory
    from app.summarizer.llm import LLMSummarizer
    from app.pipeline.digest import DigestPipeline

    settings = get_settings()
    db = await get_db()
    summarizer = LLMSummarizer(host=settings.ollama_host, model=settings.ollama_model)
    factory = FetcherFactory()

    pipeline = DigestPipeline(db=db, fetcher_factory=factory, summarizer=summarizer)
    try:
        digest = await pipeline.run(
            recipient=settings.digest_recipient,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
        )
        return _redirect(
            f"/admin/digest?msg=Digest+complete:+{digest.article_count}+articles"
        )
    except Exception as exc:
        return _error_page(f"Digest failed: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redirect(url: str) -> HTMLResponse:
    """Return a redirect response."""
    return HTMLResponse(
        content=f'<html><head><meta http-equiv="refresh" content="0;url={url}"></head></html>',
        status_code=303,
        headers={"Location": url},
    )


def _error_page(message: str) -> HTMLResponse:
    """Return a simple error page."""
    return HTMLResponse(
        content=f"""<!DOCTYPE html><html lang="en">
        {_HEAD.format(title="Error")}
        <body><div class="container">
        {_nav()}
        <div class="msg msg-err">{message}</div>
        <a href="/admin">Back to Dashboard</a>
        </div></body></html>""",
        status_code=400,
    )
