<p align="center">
  <img src="pheme-hero.png" alt="Pheme — AI-powered daily news digest" width="700">
</p>

<h1 align="center">
  <img src="pheme-icon.png" alt="" width="32" height="32" style="vertical-align: middle;">
  Pheme
</h1>

<p align="center">
  <em>Named after the Greek goddess of fame and report — she gathers, summarizes, and delivers your daily news digest.</em>
</p>

<p align="center">
  <a href="#features">Features</a> · <a href="#quick-start">Quick Start</a> · <a href="#docker">Docker</a> · <a href="#admin-ui">Admin UI</a> · <a href="#api-reference">API</a> · <a href="#configuration">Configuration</a>
</p>

---

**Pheme** is a self-hosted Python service that aggregates news from RSS feeds, Reddit, and web pages, summarizes articles using a local LLM via [Ollama](https://ollama.com), and delivers a curated HTML digest by email every morning.

She runs entirely on your own hardware — no cloud APIs, no tracking, no subscriptions.

## Features

- **Multi-source aggregation** — RSS/Atom feeds, Reddit subreddits, and generic web scraping via a pluggable fetcher architecture
- **Local LLM summarization** — powered by [Ollama](https://ollama.com); runs any model you choose (default: `qwen2.5:1.5b-instruct`)
- **Topic-based digests** — organize sources into topics with keyword matching, regex patterns, and priority-based ranking
- **Cross-topic deduplication** — each article appears in only one section, assigned to the highest-scoring topic
- **Keyword filtering** — global blocklist to suppress articles matching unwanted keywords, with configurable scope (title+preview or full text)
- **Full-text extraction** — fetches complete article content for better summaries, not just RSS snippets
- **Scheduled delivery** — daily email via APScheduler cron (default: 06:00 UTC)
- **Admin UI** — built-in dark-themed web interface for managing sources, topics, keyword blocklist, and triggering digests
- **Comprehensive tests** — 230+ tests with 80%+ coverage target

## Architecture

```
RSS Feeds ─┐
Reddit ────┤── [Fetchers]  ── [Full-text Extract] ── [Keyword Filter]
Web Pages ─┘   Strategy +      BeautifulSoup          Global blocklist
               Factory                                 (configurable)

                    ↓

              [Topic Matching] ── [Dedup] ── [Summarizer] → [Composer] → 📬
              Keyword + regex     One article   Ollama LLM    Jinja2 HTML
              scoring             per section   (local)       + plain text

                    ↓

              [Scheduler]      APScheduler cron (daily at 06:00)
```

## Quick Start

### Prerequisites

- **Python 3.12+**
- An [Ollama](https://ollama.com) instance with a model pulled:
  ```bash
  ollama pull qwen2.5:1.5b-instruct
  ```
- SMTP credentials for email delivery (Gmail [app passwords](https://support.google.com/accounts/answer/185833) work well)

### Install & Run

```bash
# Clone
git clone https://github.com/oveku/pheme.git
cd pheme

# Virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your SMTP credentials and Ollama host

# Seed example sources (optional)
python seed.py

# Start
uvicorn app.main:app --host 0.0.0.0 --port 8020
```

Pheme is now running at **http://localhost:8020**. Visit the admin UI at **/admin**.

## Docker

The simplest way to run Pheme in production:

```bash
# Configure
cp .env.example .env
# Edit .env with your settings

# Start
docker compose up -d

# Seed example sources (optional)
docker compose exec pheme python seed.py
```

### Connecting to an External Ollama Host

If Ollama runs on another machine on your network:

```dotenv
OLLAMA_HOST=http://your-ollama-host:11434
```

## Admin UI

Pheme includes a built-in admin interface at `/admin` for managing your digest without touching the API:

| Page | Path | What You Can Do |
|------|------|-----------------|
| Dashboard | `/admin` | Overview of sources, topics, and recent digests |
| Sources | `/admin/sources` | Add, view, and delete RSS/Reddit/web sources |
| Topics | `/admin/topics` | Create topics with keywords, regex patterns, and priorities |
| Digest | `/admin/digest` | Trigger a manual digest run and view send history || Settings | `/admin/settings` | Manage blocked keywords and configure filter scope |
## API Reference

### Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sources` | List all sources |
| `POST` | `/api/sources` | Add a source |
| `GET` | `/api/sources/{id}` | Get source details |
| `PUT` | `/api/sources/{id}` | Update a source |
| `DELETE` | `/api/sources/{id}` | Remove a source |

### Topics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/topics` | List all topics |
| `POST` | `/api/topics` | Create a topic |
| `GET` | `/api/topics/{id}` | Get topic details |
| `PUT` | `/api/topics/{id}` | Update a topic |
| `DELETE` | `/api/topics/{id}` | Remove a topic |
| `GET` | `/api/topics/{id}/sources` | List sources for a topic |

### Digest

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/digest/history` | Digest send history |
| `POST` | `/api/digest/trigger` | Manually trigger a digest |
| `GET` | `/health` | Health check |

### Examples

```bash
# Add an RSS source
curl -X POST http://localhost:8020/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hacker News",
    "type": "rss",
    "url": "https://hnrss.org/best",
    "category": "tech",
    "config": {"max_items": 15}
  }'

# Add a Reddit source
curl -X POST http://localhost:8020/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "r/MachineLearning",
    "type": "reddit",
    "url": "r/MachineLearning",
    "category": "ai",
    "config": {"sort": "hot", "limit": 10}
  }'

# Create a topic with keyword matching
curl -X POST http://localhost:8020/api/topics \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI & Machine Learning",
    "keywords": ["AI", "machine learning", "LLM", "neural network", "GPT"],
    "priority": 80,
    "max_articles": 10
  }'

# Trigger a digest
curl -X POST http://localhost:8020/api/digest/trigger
```

## Configuration

All settings via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5:1.5b-instruct` | LLM model for summarization |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | — | Sender email address |
| `SMTP_PASSWORD` | — | SMTP password / app password |
| `DIGEST_RECIPIENT` | — | Recipient email address |
| `DIGEST_CRON_HOUR` | `6` | Digest send hour |
| `DIGEST_CRON_MINUTE` | `0` | Digest send minute |
| `DIGEST_TIMEZONE` | `UTC` | Scheduler timezone |
| `PHEME_PORT` | `8020` | HTTP server port |
| `PHEME_DB_PATH` | `./pheme.sqlite` | SQLite database path |

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=app --cov-report=term-missing

# By category
python -m pytest tests/ -m unit
python -m pytest tests/ -m api
python -m pytest tests/ -m fetcher
python -m pytest tests/ -m pipeline
```

## Design Patterns

Pheme uses several classic design patterns:

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Strategy** | `fetchers/`, `matching.py` | Interchangeable fetchers; configurable filter scope |
| **Factory** | `FetcherFactory` | Creates the correct fetcher from source type |
| **Template Method** | `BaseFetcher.fetch()` | Defines connect → extract → normalize skeleton |
| **Singleton** | `config.py`, `database.py` | Settings and DB connection managed as singletons |
| **Pipeline** | `DigestPipeline` | Orchestrates fetch → extract → filter → match → dedup → summarize → email |

## Project Structure

```
pheme/
├── app/
│   ├── api/           # REST API routes (sources, topics, digest)
│   ├── email/         # HTML/plain-text composer + SMTP sender
│   ├── fetchers/      # RSS, Reddit, Web fetchers + factory
│   ├── pipeline/      # Digest orchestrator + topic matching + filtering + dedup
│   ├── scheduler/     # APScheduler cron job definitions
│   ├── static/        # Icons and static assets
│   ├── summarizer/    # Ollama LLM client with fallback
│   ├── templates/     # Jinja2 email templates
│   ├── ui/            # Built-in admin web interface
│   ├── config.py      # Pydantic settings from environment
│   ├── database.py    # async SQLite CRUD layer
│   ├── main.py        # FastAPI app with lifespan management
│   └── models.py      # Pydantic data models
├── tests/             # 230+ tests (pytest + pytest-asyncio)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── seed.py            # Default source seeder
└── .env.example       # Configuration template
```

## Etymology

> **Pheme** (Φήμη) was the Greek goddess — and personification — of fame, rumour, and report. She was described as having many eyes and mouths, always watching and always speaking. Fitting for a service that watches dozens of news sources and reports back with a tidy summary each morning.

## License

[MIT](LICENSE)
