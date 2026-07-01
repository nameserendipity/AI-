# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ValueCell is a community-driven, multi-agent platform for financial applications. It provides AI-powered investment agents for stock selection, fundamental research, portfolio tracking, and automated trading. Three-tier stack: Python (FastAPI) backend → React (TypeScript) frontend → optional Rust (Tauri) desktop shell.

## Dev Commands

### Backend (Python)

```bash
cd python

# Install (uv is the package manager)
uv sync

# Run server
uv run python -m valuecell.server.main

# Run all tests
uv run pytest

# Run tests in a specific area
uv run pytest valuecell/core/coordinate/tests/

# Run a single test file
uv run pytest valuecell/core/agent/tests/test_decorator.py

# Run a single test by name
uv run pytest valuecell/core/agent/tests/test_decorator.py -k "test_function_name"

# Lint
ruff check --config ./pyproject.toml .

# Format
ruff format --config ./pyproject.toml . && uv run isort .
```

### Frontend (TypeScript)

```bash
cd frontend

# Install (bun is the package manager)
bun install

# Dev server
bun run dev

# Type check
bun run typecheck

# Lint (Biome — replaces ESLint/Prettier)
bun run lint
bun run lint:fix

# Format
bun run format
bun run format:fix

# Full check (lint + format)
bun run check
bun run check:fix

# Build
bun run build
```

### Full Stack (launcher scripts from repo root)

```bash
# Linux/macOS
bash start.sh

# Windows (PowerShell)
.\start.ps1

# Options: --no-frontend, --no-backend, --help
```

## High-Level Architecture

### Python Backend (`python/valuecell/`)

The backend is organized in layers:

1. **`server/`** — FastAPI web server. Entry point at `server/main.py`. App factory at `server/api/app.py` creates the FastAPI app, registers 16+ route modules, CORS middleware, exception handlers, and initializes database + data adapters on startup. Routes are under `/api/v1/*`. Auto-generates Swagger at `/docs` in debug mode.

2. **`core/`** — Agent orchestration framework (the heart of the multi-agent system):
   - **`coordinate/`** — `AgentOrchestrator`: main async loop (triage → plan → execute → stream)
   - **`super_agent/`** — Intent triage: answers directly vs. hands off to planner
   - **`plan/`** — Planner service with human-in-the-loop (HITL) support, turns intent into execution plan
   - **`task/`** — Task executor, store, manager, temporal scheduling
   - **`agent/`** — Agent card/decorator/connect using the A2A (Agent-to-Agent) protocol
   - **`event/`** — Response routing, buffering, factory for streaming output to the frontend
   - **`conversation/`** — Conversation store (in-memory + SQLite), item store, manager
   - **`types.py`** — Core type definitions: `BaseAgent` ABC, response models (streaming, notifications, component generation, task lifecycle events), event enums

3. **`agents/`** — Concrete agent implementations:
   - **`common/trading/`** — Shared trading agent framework (base class, runtime, coordinator, stream controller, market data interfaces, strategy decision engines, exchange execution via ccxt, portfolio tracking, feature extraction, trade history)
   - **`research_agent/`** — Deep research agent (SEC filings, web search, knowledge base)
   - **`news_agent/`** — Scheduled news retrieval agent
   - **`grid_agent/`** — Grid trading strategy agent
   - **`prompt_strategy_agent/`** — Prompt-based strategy agent
   - **`astock_analysis_agent/`** — A-share market analysis agent

4. **`adapters/`** — Market data adapters abstracting data sources:
   - **`assets/`** — Yahoo Finance, AKShare (Chinese), BaoStock, with an adapter manager
   - **`astock/`** — A-share specific (CNInfo, mootdx, symbol lists, Tavily news)
   - **`models/`** — LLM model provider factory (agno-based: OpenAI, Google, Ollama, LanceDB)

5. **`config/`** — YAML config + env var loading
6. **`utils/`** — Env management, i18n, model helpers, UUID generation, port finding

### Architecture Flow

```
User Input (query + conversation_id)
  → AgentOrchestrator (core/coordinate/)
    → SuperAgent (core/super_agent/) — triage: answer directly or plan?
      → Planner (core/plan/) — decompose intent into tasks
        → Task Executor (core/task/) — execute tasks via agents
          → Agent stream() — stream responses (tool calls, reasoning, messages, components)
            → Event Response Service (core/event/) — route to conversation store + SSE stream
```

Key design: **async-first** everywhere. Agents implement `stream()` for user-initiated conversation and `notify()` for proactive push notifications. All responses stream through the event system as SSE to the frontend conversation store.

### Frontend (`frontend/src/`)

- **React 19 + React Router v7** (SSR disabled — SPA mode) with Vite
- **Tailwind CSS v4** + **shadcn/ui** (New York style) + **Radix UI** primitives
- **Zustand** for state, **TanStack React Query** for server state
- **i18next** for internationalization (multi-language support)
- Key routes: `/home` (dashboard with stock charts, watchlists), `/agent/:agentName` (chat), `/agent/:agentName/config`, `/setting/*` (models, memory, general), `/market` (agent marketplace)
- **Biome** (not ESLint/Prettier) for linting/formatting

### Desktop Shell (`frontend/src-tauri/`)

Tauri v2 Rust shell that wraps the web frontend. Spawns and manages the Python backend process (`backend.rs`). Supports deep-link, dialog, file system access, updater.

## Key Conventions (from AGENTS.md — Python)

- **Package manager**: `uv`. Virtual env in `python/.venv`.
- **Async-first**: Prefer async APIs for I/O. Use `httpx` for HTTP. Public APIs should be async.
- **Logging**: Use `loguru` with `{}` placeholders. `logger.warning` for recoverable errors, `logger.exception` only for truly unexpected errors needing stack traces.
- **Type hints**: Use everywhere. Prefer pydantic `BaseModel`, `TypedDict`, or `Protocol` over raw dicts.
- **Imports**: Avoid inline imports. Prefer qualified imports (e.g., `import pathlib` not `from pathlib import Path`). Use `TYPE_CHECKING` for type-only imports.
- **Error handling**: Keep try-except depth ≤ 2. Catch specific exceptions. Guard clauses over broad exception use.
- **Structure**: Functions ≤ 200 lines, ≤ 10 parameters (use data classes/pydantic). Separate I/O, parsing, business logic, and orchestration.
- **Booleans**: Prefer explicit `is not None` checks; avoid `value or default` when 0/empty/False is meaningful.
- **String literals**: Wrap under 100 chars. No magic numbers/strings — centralize constants.

## Key Libraries

| Library | Purpose |
|---|---|
| FastAPI + uvicorn | Web server |
| agno (phidata) | Multi-agent framework (LLM providers) |
| a2a-sdk | Agent-to-Agent protocol |
| SQLAlchemy + aiosqlite | ORM, database |
| ccxt | Crypto exchange connectivity (OKX, Binance, Hyperliquid, etc.) |
| yfinance | US market data |
| akshare / baostock | Chinese A-share market data |
| edgartools | SEC filings |
| crawl4ai | Web scraping |
| LanceDB | Vector store (knowledge base) |
| pydantic v2 | Data validation, settings |
| ECharts v6 | Charting (frontend) |
| Biome | Linting/formatting (frontend) |
