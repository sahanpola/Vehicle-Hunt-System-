# Vehicle Search Agent

A multi-agent system that searches Sri Lankan car sites every day for a user's saved search and emails the top 10 listings.

- **Backend:** FastAPI + LangGraph (agents) + OpenAI (LLM) + Tavily (scraping) + APScheduler (daily runs) + SQLite
- **Frontend:** React (Vite)

## Agent pipeline

```
User request
   └─ parse_request      LLM, structured output  → make / model / years / budget / search query
        ├─ scrape_site   one per site (parallel, LangGraph Send): Tavily extract of the site's own
        │                search URL built from the criteria (sites.py) → sanitize.py parses the car cards
        └─ collect       filter + dedupe, then split: NEW vehicles vs ones sent in earlier reports
             ├─ check_availability  sent before but missing today → open the ad: still up or gone?
             ├─ price      LLM price analysis
             ├─ condition  LLM per listing (concurrent)
             └─ value      LLM value analysis
                  └─ rank        LLM ranks top 10 NEW vehicles
                       └─ send_email  waits for rank + check_availability; LLM summary + SMTP → Daily report
```

## Project layout

```
backend/
  .env.example         secrets template (copy to .env)
  app/
    main.py            FastAPI app; starts DB + scheduler
    config.py          settings loaded from .env
    db.py              SQLAlchemy models: SearchRequest, Report
    schemas.py         API request/response models
    api/routes.py      REST endpoints
    scheduler.py       one daily cron job per active search
    history.py         remembers vehicles already analysed/sent per search (tracked_listings table)
    pipeline.py        runs the graph and saves a Report
    agents/
      graph.py         wires the nodes together (edit here to change the flow)
      state.py         shared state passed between nodes
      llm.py           OpenAI helper with structured output
      sites.py         builds each site's search URL from the criteria (add new sites here)
      sanitize.py      page text → compact product records (no LLM)
      parse_request.py, scraper.py, collect.py,
      price.py, condition.py, value.py, rank.py, send_email.py
frontend/
  src/App.jsx, src/api.js, src/components/*
```

To add an agent, write a new `async def node(state) -> dict` file in `agents/`, add its output key to `state.py`, and add it in `graph.py`.

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the keys
uvicorn app.main:app --reload --port 8000
```

`.env` values:

| Key | What |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (platform.openai.com) |
| `OPENAI_MODEL` | defaults to `gpt-5` |
| `TAVILY_API_KEY` | Tavily key (app.tavily.com) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `EMAIL_FROM` | Mail server. For Gmail, use an [App Password](https://myaccount.google.com/apppasswords). If `SMTP_USER` or `SMTP_PASSWORD` is empty, emails are skipped but reports are still saved. |
| `TIMEZONE` | Time zone for the scraping time, default `Asia/Colombo` |
| `MAX_PAGES_PER_SITE` | Result pages fetched from each site's search (default 2) |
| `MAX_LISTINGS_PER_SITE` | Tavily web-search results, only for sites without a URL builder (default 10) |
| `MAX_LISTINGS_TO_ANALYSE` | Max cars sent to the LLM agents per run (default 25) |

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

`frontend/.env` sets `VITE_API_URL` (default `http://localhost:8000`).

## Tests

Unit tests never call OpenAI, Tavily or SMTP: those are replaced with fakes, and a guard fails any test that
reaches a real client. They use a temporary SQLite database, not your `vehicle_agent.db`.

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

| File | Covers |
|---|---|
| `test_sites.py` | Search URLs built for riyasewana and ikman (filters, vehicle types, paging, fallbacks) |
| `test_sanitize.py` | Card parsing for cars, vans, motorbikes, three-wheelers; filters; dedupe; spare parts |
| `test_collect.py` | Splitting new / still listed / missing vehicles, cap and site interleaving |
| `test_availability.py` | Removed vs live ads, batching, check errors |
| `test_llm.py` | OpenAI helper: structured output, refusals, reasoning effort per model |
| `test_agents.py` | Rank, condition, email agents (what they send to the LLM and when they skip it) |
| `test_pipeline.py` | Full pipeline over three simulated days (new, price drop, sold, still listed) |
| `test_api.py` | REST endpoints, validation and scheduling |

## Usage

1. Open the UI and enter the vehicle you want (free text, e.g. "BMW 320d 2012–2016 under 9 million"), your email, the sites, and a daily time.
2. The search is saved and scheduled. It runs every day at that time.
3. Press **Run now** to run it right away. Results show in the card and are emailed.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/sites` | preset sites |
| POST | `/api/requests` | create a search `{email, vehicle_query, sites[], scrape_time:"HH:MM"}` |
| GET | `/api/requests?email=` | list searches |
| PATCH | `/api/requests/{id}` | pause/resume or change time |
| DELETE | `/api/requests/{id}` | delete a search |
| POST | `/api/requests/{id}/run` | run now |
| GET | `/api/requests/{id}/reports` | run history (latest first) |

## Daily report sections

Each search remembers every vehicle it has analysed (`tracked_listings` table, keyed by the ad URL), so each report has:

1. **New today**: vehicles never analysed before for this search, ranked top 10. Only these go to the LLM agents.
2. **Still available**: vehicles from earlier reports that are still for sale, with the price change since they were sent.
3. **No longer available**: vehicles from earlier reports whose ad has been removed. If a vehicle is missing from today's results, `check_availability` opens its ad page first (it may just have moved past the pages fetched), so only removed ads are listed here, once.

Vehicles analysed but not sent (outside the top 10) aren't analysed again. Matching vehicles beyond `MAX_LISTINGS_TO_ANALYSE` are analysed on later runs and then show up as new.

All vehicle types are supported: car, SUV, van, pickup, crew cab, motorcycle, three-wheeler, bus, lorry, heavy-duty, tractor and bicycle.

## Notes

- **Scraping:** for riyasewana.com and ikman.lk, `sites.py` builds the site's own search URL from the parsed criteria, and Tavily extract fetches that results page, so the site applies the filters itself:
  - riyasewana: `https://riyasewana.com/search.php?make=Mitsubishi&model=Lancer&vtype=cars&year=2005&year_max=2015&pricemmax=8000000&trans=Automatic`
  - ikman: `https://ikman.lk/en/ads/sri-lanka/cars/mitsubishi/lancer?money.price.maximum=8000000&numeric.model_year.minimum=2005&numeric.model_year.maximum=2015&enum.transmission=automatic`

  If the model matches nothing (e.g. "3 Series" isn't an ikman model), it retries with the make only. Other sites fall back to Tavily web search on that domain. Only the domain of the site URL you enter is used.
- **Lower LLM cost:** `sanitize.py` keeps only title, price, year, mileage, location, specs and a short description per car, drops spare parts and the paid "Top/Featured" ads for other makes, and treats mileage of 1,000 km or less as unknown (sellers' placeholders). `collect` drops wrong make, year or budget, removes duplicates, alternates between sites and caps the count before any LLM call.
- **Card limits:** search-result cards have no seller description, so they get a neutral condition score without an LLM call.
- The scheduler runs inside the API process, so keep one uvicorn worker. Daily runs only happen while the server is running.
- LLM calls use the OpenAI Responses API with structured outputs (Pydantic models).
