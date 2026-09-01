# AGENTS.md

Deep Research Agent — multi-agent LangGraph research system (supervisor + collector/validator/visualizer subagents) exposing a Flask API.

## Setup & run

- Managed with `uv` (see `uv.lock`, `.python-version` = 3.13). Prefer `uv sync` / `uv run` over `pip install -r requirements.txt`.
- No test suite exists. Verify by running the server and hitting `POST /research`.
- Run the API: `flask --app src/api/app run` (requires the `flask` CLI on PATH / venv).
- Copy `.env.example` → `.env`. `SERPAPI_API_KEY` and `POSTGRES_URL` are **required** (no defaults in `src/config/settings.py`) — the app raises on import without them, even though the Postgres store is currently disabled (commented out in `app.py`).

## Hard dependencies / gotchas

- **Google ADC file is no longer required.** Models use OpenAI-compatible endpoints configured via `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_REASONING_MODEL` in `.env` (see `src/config/llm_models.py`).
- Models are **Google Gemini** (`gemini-3-flash-preview`). The `langchain-openrouter` code in `llm_models.py` is commented out — OpenRouter is not actually used.
- `src/tools/ddg_mcp.py` runs `asyncio.run()` at import to spawn `uvx duckduckgo-mcp-server` (stdio MCP). Importing the agents/tools chain requires `uvx` available and network. The shared `tools` list is mutated via `append` across `subagents.py` and `research.py` — ordering/cumulative behavior is intentional but easy to break.
- `.env` env var names in code are `DEEP_RESEARCH=0` etc. (README's `DEEP_Research` casing is wrong — trust `settings.py`).
- Importing `src.config.*` executes module-level settings/credential/logging init, so anything touching these needs `.env` + credentials present.

## Architecture

- `src/api/app.py` — Flask `POST /research`; runs the agent synchronously via a module-level event loop; writes report to `Result.md`.
- `src/agents/research.py` — `create_research_agent()` builds the deep agent; `clean_output()` converts `[[[Title — URL]]]` citation markers to numbered `[1]` refs.
- `src/agents/subagents.py` — collector/validator/visualizer subagent factories; each wraps a graph and swallows `GraphRecursionError`.
- `src/config/prompts.py` — all system prompts (enforces collect → validate → visualize → synthesize; no answer until all subagents return).
- `src/config/agent_configs.py` — `make_store()` (Postgres, currently unused), `handle_tool_errors` middleware that lets the agent continue on tool failure.
- `src/tools/` — SerpAPI search, web scrape, and DDG MCP tools.
- `src/observability/` — Loguru daily rotation (`logs/`), Langfuse callback.

Disabled/incomplete features (currently commented out or off): Postgres store + memory routing (`make_backend`/`make_store`), `response_format=ResearchDocument` structured output, `ModelCallLimitMiddleware`. Do not assume they work if you re-enable.
