# Spartan Career Compass

LLM-based virtual assistant for SJSU students: Career Center events, counselors, and career guides (CMPE 259 Term Project).

## Setup

### 1. Python environment

```bash
cd "CMPE-259-Spartan-Career-Compass"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. PostgreSQL

- Install PostgreSQL and create a database:
  ```bash
  createdb career_compass
  ```
- Copy `.env.example` to `.env` and set `DATABASE_URL` (e.g. `postgresql://postgres:password@localhost:5432/career_compass`).

### 3. Database schema and data

```bash
python scripts/init_db.py
python scripts/load_guides.py
python scripts/scrape_all.py
```

Use `scrape_all.py` for live data from the SJSU Career Center site. Optionally run `scripts/seed_events_staff.py` only if the site is unreachable (fallback sample data).

### 4. Ollama
- Install [Ollama](https://ollama.com) and pull at least one model:
  ```bash
  ollama pull mistral:7b
  ollama pull llama3.2:3b
  ```
- Optional: in `.env` set `OLLAMA_LARGE_MODEL` and `OLLAMA_SMALL_MODEL` (e.g. `llama2:13b`, `mistral:7b`).

### 5. Adzuna (for job search later)

- Register at [Adzuna Developer](https://developer.adzuna.com/signup), then set in `.env`:
  - `ADZUNA_APP_ID`
  - `ADZUNA_APP_KEY`

## Run the app

From the project root:

```bash
streamlit run app.py
```

Open the URL shown (e.g. http://localhost:8501). Choose the model in the sidebar and ask about events, counselors, or career guides.

## Project layout

- `app.py` - Streamlit chat UI
- `config.py` - Settings from env
- `schema.sql` - PostgreSQL tables
- `scripts/init_db.py` - Apply schema
- `scripts/load_guides.py` - Ingest PDFs from `career_guides/`
- `scripts/scrape_events.py` - Scrape events from careercenter.sjsu.edu/events/
- `scripts/scrape_staff.py` - Scrape staff from careercenter.sjsu.edu/staff/
- `scripts/scrape_all.py` - Run both scrapers (use this for live data)
- `scripts/seed_events_staff.py` - Fallback sample data if site is down
- `src/agent.py` - LangGraph ReAct agent (Ollama + tools)
- `src/tools/` - DB and guide tools
