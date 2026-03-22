# Job Intelligence API

Developer-ready API for builders of job boards, career products, matching apps, and hiring analytics tools.

Turn public job listings into searchable, structured job intelligence without building your own ingestion and cleanup pipeline.

Instead of spending time on messy source data, duplicate handling, field normalization, and storage, you can start building product features on top of usable job records.

## What Problem It Solves

When job data is messy, the problem is not just technical inconvenience. It slows product delivery, creates unreliable metrics, weakens search and matching quality, and forces teams to spend time maintaining data plumbing instead of shipping user-facing features.

Teams building with job data usually run into the same issues:

- public job data arrives with inconsistent fields and uneven quality
- duplicate listings distort counts, analytics, and search results
- titles, locations, and skills are hard to standardize across records
- raw listings break downstream product logic for filtering, ranking, and dashboards
- maintaining ingestion and cleanup becomes an ongoing cost that slows product development

Job Intelligence API helps by turning public job listings into cleaner, more usable records so you can focus on the product experience instead of data maintenance.

## Who This API Is For

- **Job board builders:** You are launching a niche or regional jobs product and need searchable listings without owning the full ingestion and cleanup stack.
- **AI job matching apps:** You are building recommendations or ranking workflows and need normalized job records before you can match users to opportunities.
- **Recruiter analytics dashboards:** You are turning hiring activity into charts, benchmarks, and alerts and need cleaner records before the numbers become useful.
- **Market research tools:** You are tracking role demand, company activity, and skill trends and need structured job data instead of raw pages.
- **Career tracking apps:** You are helping users understand where the market is moving and need consistent signals around titles, locations, and skills.

## Key Features

- Launch faster with structured job data instead of raw listing pages
- Keep your dataset cleaner with built-in duplicate handling
- Build search, matching, and analytics features on normalized job records
- Turn stored listings into usable market signals with skills, company, and location insights
- Integrate quickly with simple API key auth and predictable JSON responses
- Start small and stay practical with a beginner-friendly setup, Swagger docs, and Docker support

## Start Building Faster

This API helps developers skip the slowest early work in job-data products:

- source ingestion
- messy field cleanup
- duplicate handling
- normalization and basic enrichment

That means you can spend more time building job search, matching, dashboards, or career features, and less time maintaining raw listing pipelines.

## Example Use Cases

### 1. Job Board Builders

Launch a niche job board faster by pulling structured job listings into your own frontend without building a custom ingestion stack first.

Business value: you can get a searchable job experience live sooner and spend more effort on audience, distribution, and UX.

### 2. AI Job Matching Apps

Feed normalized job records into recommendation systems, ranking models, or candidate matching flows with less cleanup work.

Business value: your matching logic starts from cleaner titles, skills, and job signals instead of inconsistent raw records.

### 3. Market Research Tools

Track which job titles, skills, companies, and locations are appearing most often in public hiring data.

Business value: you can turn job listings into faster market reporting without first building a separate normalization layer.

### 4. Recruiter Analytics Dashboards

Build dashboards that monitor hiring activity, role patterns, and company movement across your target market.

Business value: cleaner underlying data makes trend charts, benchmarks, and internal reports more trustworthy.

### 5. Career Tracking Apps

Help users follow demand for certain roles, see which skills appear most often, and watch how job signals change over time.

Business value: better job intelligence makes the product more useful to end users and easier to revisit regularly.

## Best First Use Cases

- Add a searchable jobs page to your product with `/jobs/search` and `/jobs/{job_id}`.
- Build a simple skills and companies trend dashboard with `/insights/skills` and `/insights/companies`.
- Feed normalized job records into a recommendation, ranking, or AI matching workflow without first building data cleanup logic.

## Why This API Instead of Scraping Yourself?

- Faster time to market
- Less maintenance work on parsing and cleanup
- Structured output you can use immediately
- Deduplication built in
- Search, detail, and insight endpoints in one product
- Cleaner path to marketplace publishing than a custom internal scraper

## What Makes This API Different?

- It is designed as a usable product API, not just a scraping script
- It returns standardized job records instead of raw source fields
- It stores and deduplicates records so your backend is more stable
- It includes insight endpoints, not just listing endpoints
- It is simple enough for beginners to integrate and extend

## Example API Calls and Responses

Base URL examples below use local development:

```text
http://127.0.0.1:8000
```

All protected endpoints use the same top-level response envelope:

```json
{
  "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5100",
  "timestamp": "2026-03-22T09:00:00Z",
  "data": {},
  "error": null
}
```

### Search Jobs

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/jobs/search?q=engineer&remote=true&limit=2"
```

```json
{
  "request_id": "f3fbf2dc-bf5e-4dc0-b706-06ecb93ebcb7",
  "timestamp": "2026-03-22T09:00:00Z",
  "data": {
    "query": "engineer",
    "filters": {
      "location": null,
      "remote": true,
      "employment_type": null,
      "seniority": null
    },
    "pagination": {
      "page": 1,
      "limit": 2,
      "total_pages": 1,
      "total_results": 2
    },
    "count": 2,
    "jobs": [
      {
        "id": "8eb5a31de77f3c2a3fbb3f69",
        "source": "remoteok",
        "source_job_id": "1001",
        "source_job_url": "https://remoteok.com/remote-jobs/1001",
        "title": "Senior Python Backend Engineer",
        "normalized_title": "Python Backend Engineer",
        "company": "Acme",
        "location_raw": "Berlin, Germany",
        "location_city": "Berlin",
        "location_country": "Germany",
        "remote_type": "remote",
        "employment_type": "full_time",
        "seniority_level": "senior",
        "salary_text": "$100k - $120k",
        "description_snippet": "Build FastAPI services with Python, Docker, and AWS.",
        "skills": ["aws", "docker", "fastapi", "python"],
        "posted_at": "2026-03-20T10:00:00Z",
        "freshness_days": 2
      },
      {
        "id": "af786baddfd5dc547c22808f",
        "source": "remoteok",
        "source_job_id": "1002",
        "source_job_url": "https://remoteok.com/remote-jobs/1002",
        "title": "Platform Engineer",
        "normalized_title": "Platform Engineer",
        "company": "Northstar",
        "location_raw": "Remote",
        "location_city": null,
        "location_country": null,
        "remote_type": "remote",
        "employment_type": null,
        "seniority_level": null,
        "salary_text": null,
        "description_snippet": "Work on cloud infrastructure, Kubernetes, and backend systems.",
        "skills": ["backend", "kubernetes"],
        "posted_at": "2026-03-21T08:15:00Z",
        "freshness_days": 1
      }
    ]
  },
  "error": null
}
```

### Get One Job

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/jobs/8eb5a31de77f3c2a3fbb3f69"
```

```json
{
  "request_id": "78f4d40f-8d8e-45a5-8a12-cd2f4c5b3b11",
  "timestamp": "2026-03-22T09:00:00Z",
  "data": {
    "job": {
      "id": "8eb5a31de77f3c2a3fbb3f69",
      "source": "remoteok",
      "source_job_id": "1001",
      "source_job_url": "https://remoteok.com/remote-jobs/1001",
      "title": "Senior Python Backend Engineer",
      "normalized_title": "Python Backend Engineer",
      "company": "Acme",
      "location_raw": "Berlin, Germany",
      "location_city": "Berlin",
      "location_country": "Germany",
      "remote_type": "remote",
      "employment_type": "full_time",
      "seniority_level": "senior",
      "salary_text": "$100k - $120k",
      "description_snippet": "Build FastAPI services with Python, Docker, and AWS.",
      "skills": ["aws", "docker", "fastapi", "python"],
      "posted_at": "2026-03-20T10:00:00Z",
      "freshness_days": 2
    }
  },
  "error": null
}
```

### Get Skill Insights

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/insights/skills?limit=5"
```

```json
{
  "request_id": "53f9d0b6-7f57-4d49-b01e-f0f54ee31d0d",
  "timestamp": "2026-03-22T09:00:00Z",
  "data": {
    "dimension": "skills",
    "count": 5,
    "items": [
      { "name": "go", "count": 2 },
      { "name": "machine learning", "count": 2 },
      { "name": "kubernetes", "count": 2 },
      { "name": "sql", "count": 1 },
      { "name": "linux", "count": 1 }
    ]
  },
  "error": null
}
```

### Get Company Insights

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/insights/companies?limit=5"
```

Example result: top companies currently seen in the stored dataset.

### Get Location Insights

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/insights/locations?limit=5"
```

Example result: top normalized job locations currently seen in the stored dataset.

## Authentication

All product endpoints use API key authentication through the `X-API-Key` header.

```bash
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/jobs/search?limit=5"
```

Behavior:

- missing API key returns `401`
- invalid API key returns `403`
- `/docs`, `/redoc`, and `/openapi.json` stay accessible for evaluation and integration

## Pricing Draft

Simple draft pricing for marketplace positioning.

| Plan | Monthly Requests | Rate Limit | Access |
| --- | ---: | ---: | --- |
| Free | 1,000 | 10 requests/minute | Core search, job detail, basic insight access |
| Pro | 25,000 | 120 requests/minute | Full standard endpoints, better throughput, production use |
| Ultra | 250,000 | 600 requests/minute | High-volume usage, priority support, marketplace-ready scale |

### Best For

- **Free:** Best for testing the API, early prototypes, and validating a product idea.
- **Pro:** Best for real products in active development that need steady usage and full standard access.
- **Ultra:** Best for higher-volume apps, shared dashboards, and teams that expect heavier traffic.

## Rate Limits

Rate limits are not enforced in code yet, but the commercial model is ready for them.

- Free: conservative request cap for exploration and demos
- Pro: balanced cap for production integration
- Ultra: higher throughput for larger product workloads

This keeps the product easy to price on marketplaces such as RapidAPI while leaving room for future quota enforcement.

## Data Freshness

Job Intelligence API currently works from public job sources and on-demand ingestion.

- freshness depends on public source availability
- data is refreshed when search ingestion runs
- this version is not a continuous enterprise crawl network
- `freshness_days` gives a simple signal for how recent a listing appears to be

## Limitations and Disclaimers

- This version focuses on public job listings only
- Source coverage is intentionally limited in the current version
- Normalization is heuristic and best-effort
- Skill extraction is keyword-based, not semantic understanding
- SQLite is suitable for this version but not a high-scale multi-writer database
- Public source changes can affect what data is available at a given moment

## Quick Start

### Run Locally

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

### Run with Docker

```bash
docker build -t job-intelligence-api .
docker run --rm -p 8000:8000 --env-file .env job-intelligence-api
```

### Required Environment Variables

- `API_KEYS`: comma-separated list of valid API keys

Helpful optional variables:

- `PORT`: defaults to `8000`
- `SQLITE_DB_PATH`: defaults to `data/jobs.db`
- `SOURCE_BASE_URL`: defaults to the current public job source
- `LOG_LEVEL`: defaults to `INFO`

### First Requests to Try

```bash
curl http://127.0.0.1:8000/healthz
curl -H "X-API-Key: your_api_key_here" http://127.0.0.1:8000/health
curl -H "X-API-Key: your_api_key_here" "http://127.0.0.1:8000/jobs/search?limit=5"
```

Swagger UI:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Marketplace Positioning Note

This project is already structured like a sellable API product:

- clear authentication model
- stable response envelope
- search, detail, and insight endpoints
- Docker-ready deployment path
- beginner-friendly developer experience

That makes it a strong starting point for RapidAPI-style publishing, partner demos, or internal product validation.
