<p align="center">
  <img src="pheme-hero.png" alt="Pheme - Your Daily News Digest" width="600">
</p>

<h1 align="center">
  <img src="pheme-icon.png" alt="" width="32" height="32" style="vertical-align: middle;">
  Pheme
</h1>

<p align="center">
  <em>The news lady who gathers, summarizes, and delivers your daily digest.</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#docker">Docker</a> &middot;
  <a href="#api">API</a> &middot;
  <a href="#configuration">Configuration</a> &middot;
  <a href="#admin-ui">Admin UI</a>
</p>

---

**Pheme** (named after the Greek goddess of fame and report) is a self-hosted Python service that aggregates news from RSS feeds, summarizes articles using a local LLM via [Ollama](https://ollama.com), and delivers a curated HTML digest by email every morning.

She runs entirely on your own hardware -- no cloud APIs, no tracking, no subscriptions.

## Features

- **Multi-source aggregation** -- RSS feeds, with extensible fetcher architecture for Reddit and web scraping
- **Local LLM summarization** -- powered by Ollama; runs any model you choose (default: `qwen2.5:1.5b-instruct`)
- **Topic-based digests** -- group sources into topics (e.g. "Tech News", "Norwegian News") for organized digests
- **Scheduled delivery** -- daily email via APScheduler cron (default: 06:00 UTC)
- **Full-text extraction** -- fetches complete article content for better summaries, not just RSS snippets
- **Admin UI** -- built-in web interface for managing sources, topics, and triggering digests
- **204 tests** -- comprehensive test suite with 80%+ coverage target

## Architecture

```
RSS Feeds / Web Sources
        |
    [Fetchers]       Strategy + Factory pattern
        |
  [Full-text Extract] trafilatura / BeautifulSoup
        |
   [Summarizer]      Ollama LLM (local, private)
        |
    [Composer]       HTML + plain-text email
        |
  [Email Sender]     SMTP (Gmail, Fastmail, etc.)
        |
   [Scheduler]       APScheduler cron (daily)
```

## Quick Start

### Prerequisites

- Python 3.12+
- An [Ollama](https://ollama.com) instance with a model pulled (e.g. `ollama pull qwen2.5:1.5b-instruct`)
- SMTP credentials for sending email (Gmail app passwords work well)

### Run Locally

```bash
# Clone and set up
git clone https://github.com/your-username/pheme.git
cd pheme

python -m venv .venv
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows

pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your SMTP credentials and Ollama host

# Seed example sources (optional)
python seed.py

# Start
uvicorn app.main:app --host 0.0.0.0 --port 8020
```

Pheme is now running at `http://localhost:8020`. Visit the admin UI at `http://localhost:8020/ui`.

## Docker

The easiest way to run Pheme:

```bash
# Configure
cp .env.example .env
# Edit .env with your settings

# Start
docker compose up -d

# Seed example sources (optional)
docker compose exec pheme python seed.py
```

### Docker Compose with external Ollama

If Ollama runs on another host, set `OLLAMA_HOST` in your `.env`:

```dotenv
OLLAMA_HOST=http://your-ollama-host:11434
```

## Admin UI

Pheme includes a built-in admin interface at `/ui` for managing sources, topics, and triggering digests without touching the API directly.

## API

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
| `GET` | `/api/topics/{id}/sources` | List sources in a topic |

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
    "name": "TLDR Tech",
    "type": "rss",
    "url": "https://tldr.tech/api/rss/tech",
    "category": "tech"
  }'

# Create a topic
curl -X POST http://localhost:8020/api/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "Tech News", "description": "Technology and software"}'

# Trigger a digest manually
curl -X POST http://localhost:8020/api/digest/trigger
```

## Configuration

All settings are configured via environment variables (or a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5:1.5b-instruct` | LLM model for summarization |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | -- | Email sender address |
| `SMTP_PASSWORD` | -- | App password |
| `DIGEST_RECIPIENT` | -- | Email recipient |
| `DIGEST_CRON_HOUR` | `6` | Digest send hour (UTC) |
| `DIGEST_CRON_MINUTE` | `0` | Digest send minute |
| `DIGEST_TIMEZONE` | `UTC` | Scheduler timezone |
| `PHEME_PORT` | `8020` | API port |
| `PHEME_DB_PATH` | `./pheme.sqlite` | SQLite database path |

## Testing

```bash
# Run all 204 tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Specific markers
python -m pytest tests/ -m unit
python -m pytest tests/ -m api
python -m pytest tests/ -m fetcher
```

## Design

Pheme uses several Gang of Four design patterns:

- **Strategy** -- fetcher types (RSS, Reddit, Web) are interchangeable
- **Factory** -- `FetcherFactory` creates the right fetcher based on source type
- **Template Method** -- `BaseFetcher.fetch()` defines the algorithm skeleton
- **Observer** -- pipeline notifies components at each stage
- **Singleton** -- database connection and config managed as singletons

## Project Structure

```
pheme/
├── app/
│   ├── api/           # REST API routes (sources, topics, digest)
│   ├── email/         # Composer + SMTP sender
│   ├── fetchers/      # RSS, Reddit, Web fetchers + factory
│   ├── pipeline/      # Digest orchestrator (fetch → summarize → email)
│   ├── scheduler/     # APScheduler cron jobs
│   ├── static/        # Icons and static assets
│   ├── summarizer/    # Ollama LLM client
│   ├── templates/     # Jinja2 email templates (HTML + plain text)
│   ├── ui/            # Built-in admin web interface
│   ├── config.py      # Pydantic settings from environment
│   ├── database.py    # SQLite/aiosqlite CRUD layer
│   ├── main.py        # FastAPI app with lifespan management
│   └── models.py      # Pydantic data models
├── tests/             # 204 tests (pytest + pytest-asyncio)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── seed.py            # Example source seeder
└── .env.example       # Configuration template
```

## License

MIT
