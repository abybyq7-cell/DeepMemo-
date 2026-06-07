# Architecture

DeepMemo is organized as a small but complete LLM application. The main design goal is to keep agent reasoning, tools, persistence, and UI boundaries clear.

## System Overview

```text
User
  |
  v
Streamlit Frontend
  |
  v
FastAPI Backend / Local Fallback Client
  |
  v
LearningEngine
  |
  +-- Topic Intake Modules
  |     +-- TopicNormalizer
  |     +-- TopicClassifier
  |     +-- ScopeInference
  |     +-- FrameworkBuilder
  |
  +-- LearningPathOrchestrator
  |     +-- MemoryStore
  |
  +-- Question Generator
  +-- Answer Evaluator
  +-- Explanation Generator
  |
  v
SQLite + JSON cache + FSRS scheduler
```

## Main Components

### Frontend

The `frontend/` package contains the Streamlit entrypoint and page views:

- daily practice
- notes
- mistakes
- knowledge library
- settings

### Backend

The `backend/` package exposes the model features as HTTP APIs:

- `GET /health`
- `POST /generate`
- `POST /evaluate`
- `POST /explain`

The web app can call the backend through `tools.utils.api_client`. If the backend is not available, the client can fall back to local function calls.

### Agent Workflow

The core workflow lives in `ai_tutor.py`, `tools/topic_intake/`, and `memory/learning_path/`.

The learning path flow is staged:

1. Normalize user topic.
2. Classify topic type.
3. Infer subject scope.
4. Build a learning framework.
5. Convert the framework into a path.
6. Store or reuse memory.

This staged workflow is easier to debug than a single large prompt.

### Tools and Memory

DeepMemo currently uses custom Tool/Skill-style orchestration. The main capabilities are:

- learning path generation
- question generation
- answer evaluation
- explanation generation
- mistake logging
- review queue retrieval
- question cache management

The next step is to expose these capabilities as standard function-calling tools with explicit JSON schemas.

### Persistence

SQLite tables include:

- `flashcards`
- `mistake_logs`
- `study_logs`
- `study_notes`
- `custom_questions`

JSON files are used for question cache, user preferences, and learning path memory.

## Reliability Design

- LLM JSON parsing with fallback.
- Provider routing through environment variables.
- Retry behavior for transient model API failures.
- Local cache for generated questions.
- FSRS-based scheduling for review dates.
- pytest coverage for workflow, config, cache, and persistence modules.

## Production Gaps

The project is still a portfolio demo. Before production use, it should add:

- authentication
- user-level data isolation
- trace logging
- standard function calling
- RAG over learning materials
- evaluation set and regression dashboard
- deployment pipeline
