# DeepMemo

DeepMemo is an AI-assisted learning agent that turns a study topic into a complete learning loop:

```text
Topic input -> topic understanding -> learning path planning -> question generation
-> answer evaluation -> mistake logging -> spaced repetition review
```

The project is designed as a portfolio-grade LLM application for education scenarios. It demonstrates agent workflow design, custom tool/skill orchestration, structured LLM outputs, memory reuse, FastAPI services, Streamlit UI, SQLite persistence, FSRS scheduling, Docker packaging, and pytest coverage.

## Why This Project Matters

Most LLM demos stop at "ask a model and show the answer". DeepMemo pushes the model into a product workflow:

- It plans a learning path before generating questions.
- It stores learning state instead of treating every request as stateless.
- It uses a mistake notebook and review queue to close the learning loop.
- It separates UI, API, workflow orchestration, memory, and tools.
- It includes fallback logic, model routing, cache, tests, and Docker setup.

This makes it close to real AI tutor, vocabulary learning, question generation, and auto-grading products.

## Key Features

- **Learning Agent Workflow**: staged topic normalization, topic classification, scope inference, framework building, and learning path orchestration.
- **Question Generation**: creates technical practice questions for a selected sub-topic.
- **Answer Evaluation**: evaluates user answers and returns concise feedback.
- **Mistake Memory**: records wrong answers and retrieves recent mistakes by topic.
- **Spaced Repetition**: uses FSRS-style scheduling to plan next review dates.
- **Structured Output Handling**: parses and validates JSON-like LLM responses with fallback behavior.
- **Model Provider Routing**: supports OpenAI SDK compatible providers such as DeepSeek and Kimi.
- **Full-stack Demo**: Streamlit frontend plus FastAPI backend.
- **Engineering Hygiene**: Docker, environment config, local healthcheck, and pytest tests.

## Architecture

```text
DeepMemo/
  backend/             FastAPI API and scheduling engine
  frontend/            Streamlit app and page views
  tools/
    topic_intake/      LLM modules for topic analysis and framework building
    utils/             config, database, API client, cache, styles, session helpers
  memory/
    learning_path/     learning path orchestrator and reusable memory store
  tests/               pytest test suite
  docs/                architecture, API, config, roadmap
  scripts/             healthcheck and local maintenance helpers
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the detailed system design.

## Tech Stack

- Python 3.10+
- Streamlit
- FastAPI + Uvicorn
- OpenAI Python SDK compatible APIs
- DeepSeek / Kimi compatible model routing
- SQLite
- FSRS
- HTTPX
- pytest
- Docker / docker-compose

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```powershell
copy .env.example .env
```

Set at least:

```text
DEEPSEEK_API_KEY=your_api_key_here
```

Run the web app:

```powershell
python main.py web
```

Run the API service:

```powershell
python main.py api
```

Run a local healthcheck:

```powershell
python main.py healthcheck
```

## API

When the backend is running at `http://localhost:8000`:

- `GET /health`
- `POST /generate`
- `POST /evaluate`
- `POST /explain`

Example:

```json
{
  "topic": "linear algebra",
  "count": 5,
  "user_context": {
    "ai_provider": "deepseek"
  }
}
```

## Docker

```powershell
docker compose build
docker compose up
```

Services:

- Web: `http://localhost:8501`
- API: `http://localhost:8000`

## Tests

```powershell
pytest
```

The test suite covers cache behavior, user preferences, scheduling, custom questions, model routing, topic intake modules, and learning path orchestration.

## Roadmap

- Convert the current custom Tool/Skill orchestration into standard function-calling schemas.
- Add RAG over vocabulary, notes, and question bank documents.
- Add tool-call trace logs and evaluation dashboards.
- Add user authentication and multi-user memory isolation.
- Deploy a public demo and record a walkthrough video.

## Portfolio Notes

This repository is a cleaned public portfolio version. Runtime databases, local caches, API keys, and generated data are intentionally excluded.
