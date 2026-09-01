# SPEC: FastAPI Migration + Config Externalization

**Date**: 2026_09_01
**Status**: Approved (design + verification plan)
**Scope owner**: Deep Research Agent

## Objective

Replace the Flask API layer (`src/api/app.py`) with a FastAPI endpoint while preserving the existing `POST /research` request/response contract, and externalize all hardcoded runtime values (GCP project, Gemini model names, credentials path, output paths, observability metadata) into `AgentSettings` backed by `.env`.

## Scope

- Rewrite `src/api/app.py` as a FastAPI application.
- Add an async `POST /research` endpoint using FastAPI's native async support (remove the manual module-level event loop).
- Add Pydantic request/response models matching the current wire format (`{content, references}`).
- Add CORS support via FastAPI middleware.
- Move hardcoded values into `AgentSettings` (`.env`).
- Update dependency manifests (`pyproject.toml`, `requirements.txt`, `uv.lock`) and `README.md` for FastAPI + uvicorn.
- Update `.env.example` with the new configuration keys.

## Assumptions

- `SERPAPI_API_KEY` and `POSTGRES_URL` remain required (the app raises on import without them, as today).
- The Gemini credentials file is still required at import time, but its path becomes configurable via settings instead of being hardcoded relative to the config directory.
- The supervisor-subagent core (agents, subagents, tools, prompts) is unchanged.
- FastAPI and uvicorn (with `[standard]` extras) will be added to the dependency set; Flask, flask-cors, and the stray `flask-core` entry will be removed.
- The report output path and `.env` file are both anchored to the project root, so the server is launched from the project root (as documented); anchoring makes CWD-independent resolution safe.
- The unused `ResearchDocument` model and the dead `store` parameter/argument are removed in this change (per spec discussion).

## Constraints

- Preserve the exact `POST /research` contract: request `{"query": str}`, response `{"content": str, "references": {title: number}}`.
- Preserve the `Result.md` side-effect (writing the cleaned markdown report), but its path becomes configurable.
- Preserve error behavior: empty/missing query → 400; uncaught exception → 500 `{"status":"error","message":...}`.
- Config-driven values must have sensible defaults so `.env` remains optional for the newly added keys.

## Approach Decision

**Selected**: FastAPI with a native `async def` endpoint and Pydantic models.

- FastAPI's async support lets the agent's `ainvoke` await naturally without a manual event loop, removing the module-level loop and `run_until_complete` workaround.
- Pydantic models give automatic request validation and OpenAPI schema generation.
- CORS is configured declaratively via `CORSMiddleware`.

**Rejected alternative**: Preserve the existing module-level event loop wrapped in a FastAPI route. This keeps the fragile event-loop management and gains none of FastAPI's async/validation benefits.

**Rejected alternative**: Expand the API surface (e.g., streaming, new endpoints). YAGNI — the current contract is sufficient; expanding is out of scope.

## Implementation Decisions

### Result file path behavior
- `RESULT_OUTPUT_PATH` is resolved **relative to the project root**, not the current working directory, so the report is written to a stable location regardless of where uvicorn is launched.
- The configured path's **parent directory is auto-created** (`Path.parent.mkdir(parents=True, exist_ok=True)`) before writing, so paths like `reports/result.md` work without pre-creating the directory.
- Implement as a helper that joins the project root (resolved from `src/api/app.py` via its own location) with the configured path.

### `.env` file discovery
- The `.env` file is **anchored to the project root** and loaded via an absolute path in `SettingsConfigDict(env_file=<project_root>/.env)`, instead of the current CWD-relative `env_file=".env"`.
- This keeps settings reliable regardless of the launch directory, consistent with the result-path anchoring decision.

### CORS origins scope
- Use `CORSMiddleware` with **`allow_origins=["*"]`** and **no credentials** (`allow_credentials=False`), matching the current Flask `CORS(app)` default (all origins, no credentials).
- No new settings key is added for CORS origins.

### References schema & dead-code cleanup
- `ResearchResponse.references` is typed **`dict[str, int]`**, matching the wire format exactly.
- **Remove the unused `ResearchDocument` model** (`src/models/response_model.py`) as part of this change.
- **Remove the dead `store` argument and parameter**: drop the unused `store` parameter from `create_research_agent()`'s signature (it is never referenced in the body at `src/agents/research.py:16`) and update the single call site `create_research_agent(settings, "store")` to `create_research_agent(settings)`.
- **Remove dead `make_store`/`make_backend` imports**: drop the unused `make_store` import in `src/api/app.py:15` (only used in a commented-out line) and the unused `make_backend` import in `src/agents/research.py:8` (only referenced in a commented-out `backend=make_backend` line). The `make_store`/`make_backend` definitions in `src/config/agent_configs.py` remain (Postgres store/memory routing is still a disabled, future feature), but their imports from the active code paths are removed.

### Run command & dependency pinning
- Add **`uvicorn[standard]`** and **FastAPI** as main runtime dependencies in `pyproject.toml`; remove **Flask, flask-cors, and the stray `flask-core`** entry (the current `flask-core>=2.9.0` line at `pyproject.toml:10` is a leftover typo and goes away with the Flask removal).
- Apply the same add/remove to **`requirements.txt`**: remove `flask[async]` and `flask-cors` (lines 9-10) and add `fastapi` and `uvicorn[standard]`, keeping it consistent with `pyproject.toml`; regenerate `uv.lock` accordingly.
- Add a **`[project.scripts]` console-script entrypoint** named **`deepagent-api`** pointing to a `main()` in `src/api/app.py` that runs uvicorn (e.g. `deepagent-api = "src.api.app:main"`), so the server runs via `uv run deepagent-api`.
- Update `README.md` to replace the `flask --app src/api/app run` instructions (`README.md:83`) and the flask dependency mentions (`README.md:144-145`) with the new uvicorn command and FastAPI/uvicorn entries.

### Planner's Discretion
- The exact console-script `main()` implementation (whether it reads `--reload`, host/port args, etc.) — the planner has flexibility, but the default should be a plain `uvicorn.run("src.api.app:app")` entrypoint.
- The precise helper location for resolving the project root (inline in `app.py` vs. a small utility) — planner's choice.

## Code Context

### Reusable Assets
- `src/observability/logging.py` — loguru `logger` already initialized and used for `logger.exception(...)`; the new endpoint reuses it directly for error logging. Its log-file path (`logs/...`) is the value externalized to `settings.LOGS_DIR`.
- `src/observability/langfuse_config.py` — `langfuse_handler` (`CallbackHandler`) is reused unchanged for the callbacks in the `RunnableConfig`.
- `src/agents/research.py` — `create_research_agent()` and `clean_output()` are reused unchanged (except the `store` param removal); the endpoint calls them exactly as today.

### Established Patterns
- Settings are defined as Pydantic `BaseSettings` fields with `@lru_cache get_settings()` (`src/config/settings.py:25-27`); new keys follow the same pattern and keep defaults so `.env` stays optional for them.
- Error behavior mirrors the current Flask handler: empty query → 400 with "No query found"; uncaught exception → 500 `{"status":"error","message":"Internal server error"}` and `logger.exception(...)`.
- The report write uses `open('Result.md','w',encoding='utf-8')` (`src/api/app.py:61`); this becomes a path anchored to project root with auto-created parents.

### Integration Points
- `src/api/app.py` — the whole rewrite; becomes the FastAPI app, async `POST /research`, global exception handler, CORS, and the new `main()` console-script entrypoint.
- `src/api/schemas.py` — new file; `ResearchRequest` and `ResearchResponse` Pydantic models.
- `src/config/settings.py` — extended `AgentSettings` with the externalized values (GCP project, credentials path, model names, result path, logs dir, langfuse metadata) and the project-root-anchored `.env` path.
- `src/config/llm_models.py` — reads `GCP_PROJECT_ID`, `GEMINI_CREDENTIALS_FILE`, `GEMINI_MODEL`, `GEMINI_REASONING_MODEL` from `get_settings()` instead of hardcoded `PROJECT`/`CREDENTIALS_FILE`/inline names (`llm_models.py:20-21,30,39`).
- `src/models/response_model.py` — deleted (unused `ResearchDocument`).
- `src/agents/research.py:16` — `store` parameter removed from `create_research_agent()`; call site `src/api/app.py:24` updated.

## Architecture

The change is confined to the API and configuration layers. The supervisor-subagent research core is untouched:

- `src/api/app.py` — FastAPI app; async `POST /research`; exception handler; CORS.
- `src/api/schemas.py` — Pydantic request/response models.
- `src/config/settings.py` — extended `AgentSettings` with all externalized values.
- `src/config/llm_models.py` — reads project/model/credentials path from settings.
- `src/observability/logging.py` — reads log directory from settings.

## Components

### 1. `src/config/settings.py`
Extend `AgentSettings` with:
- `GCP_PROJECT_ID: str` (default `"catalan-dev-484209"`)
- `GEMINI_CREDENTIALS_FILE: str` (default resolved path to `src/application_default_credentials.json`)
- `GEMINI_MODEL: str` (default `"gemini-3-flash-preview"`)
- `GEMINI_REASONING_MODEL: str` (default `"gemini-3-flash-preview"`)
- `RESULT_OUTPUT_PATH: str` (default `"Result.md"`)
- `LOGS_DIR: str` (default `"logs"`)
- Langfuse metadata: `LANGFUSE_TAGS` (default `["deepagent"]`), `LANGFUSE_CALL_TYPE` (default `"deepagent"`)

### 2. `src/config/llm_models.py`
- Remove hardcoded `PROJECT`, `CREDENTIALS_FILE`, and inline model names.
- Read values from `get_settings()`.
- `create_reasoning_model(reasoning_effort)` uses `GEMINI_REASONING_MODEL`; `create_model()` uses `GEMINI_MODEL`; both use `GCP_PROJECT_ID` and `GEMINI_CREDENTIALS_FILE`.

### 3. `src/observability/logging.py`
- Use `settings.LOGS_DIR` for the log file path instead of the hardcoded `logs/`.

### 4. `src/api/schemas.py`
- `ResearchRequest(BaseModel)`: `query: str`
- `ResearchResponse(BaseModel)`: `content: str`, `references: dict[str, int]`

### 5. `src/api/app.py`
- FastAPI `app = FastAPI()` with `CORSMiddleware`.
- `@app.post("/research")` as `async def research(payload: ResearchRequest)`.
- Build `RunnableConfig` (thread_id, callbacks, metadata) from settings-driven values.
- `await deepagent.ainvoke({"messages": [HumanMessage(payload.query)]}, config=config)`.
- `clean_output` → write markdown to `settings.RESULT_OUTPUT_PATH` → return `ResearchResponse`.
- `@app.exception_handler(Exception)` returning `{"status":"error","message":"Internal server error"}` with status 500.
- Raise `HTTPException(400)` when `query` is empty.

## Data Flow

```
POST /research {query}
  → ResearchRequest validation
  → build RunnableConfig (thread_id, langfuse callbacks, metadata)
  → await deepagent.ainvoke(messages=[HumanMessage(query)])
  → result["messages"][-1].content[0]["text"]
  → clean_output() → (content, references)
  → write content to RESULT_OUTPUT_PATH
  → return ResearchResponse {content, references}
```

## Error Handling

- Empty/missing `query` → `HTTPException(400, "No query found")`.
- Uncaught exceptions in the endpoint → logged via `logger.exception` and returned as `500 {"status":"error","message":"Internal server error"}` through the global exception handler (mirrors current Flask behavior).
- Agent-level tool errors remain handled by `handle_tool_errors` middleware (unchanged).

## Risks

- **FastAPI/uvicorn not currently installed** — requires dependency updates and lockfile regeneration.
- **Async model invocation in a long-running request** — the agent can take a long time; no timeout/streaming is added in this change.
- **Import-time side effects** — `llm_models`, `settings`, `ddg_mcp` (spawns `uvx`), and `logging` execute at import; moving values to settings must not break the required-credential import behavior.
- **Response shape mismatch** — `references` is a dict on the wire while the existing `ResearchDocument` model declares `List[str]`; the new `ResearchResponse` must match the actual wire format (dict). This is resolved by deleting the unused `ResearchDocument` model as part of this change (see Implementation Decisions › References schema & dead-code cleanup), so the stale `List[str]` declaration cannot be mistaken for the contract.

## Verification Plan

Success criteria → test category → level → key scenarios:

| Success criterion | Test category | Level | Key scenarios |
|---|---|---|---|
| `POST /research` returns `{content, references}` | Functional correctness | E2E/Integration | Valid query → 200; `content` is str; `references` maps title→int |
| Empty/missing query rejected | Error handling | Integration | Missing/blank query → 400 |
| Report written to configured path | Functional correctness | Integration | `RESULT_OUTPUT_PATH` honored; markdown file created |
| `clean_output` citation conversion | Functional correctness | Unit | `[[[Title — URL]]]` → `[1]`; dedup; numbering order |
| Model/project/credentials from config | Config correctness | Unit | `AgentSettings` values propagate; no hardcoded GCP project/model strings |
| Logs directory configurable | Config correctness | Integration | `LOGS_DIR` honored; log file created there |
| CORS enabled | Integration contract | Integration | Preflight `OPTIONS` returns CORS headers |
| Uncaught exception → 500 JSON | Error handling | Integration | Forced error → `500 {"status":"error","message":...}` |
| App boots via uvicorn | Deployment | Manual/E2E | `uvicorn src.api.app:app` starts; `/docs` served |

**Not tested (acknowledged gaps)**:
- Live LLM agent invocation (requires Gemini credentials + network).
- DDG MCP spawn (`asyncio.run` at import).
- Postgres store (disabled/out of scope).

### Traceability

| Success criterion | Design section | Verification item |
|---|---|---|
| Same `{content, references}` contract | Data Flow, Components (5) | Functional correctness (E2E) |
| Empty query → 400 | Error Handling | Error handling (Integration) |
| Configurable output path | Components (1) | Functional correctness (Integration) |
| Citation conversion preserved | Components (5), Data Flow | Unit (clean_output) |
| Model/project/creds from config | Components (2) | Config correctness (Unit) |
| Configurable logs dir | Components (3) | Config correctness (Integration) |
| CORS | Components (5) | Integration contract (Integration) |
| 500 JSON on error | Error Handling | Error handling (Integration) |
| FastAPI boots | Components (5) | Deployment (Manual/E2E) |

## Out of Scope

- Changing the supervisor-subagent architecture, tools, or prompts.
- Streaming, new endpoints, or expanding the API surface.
- Re-enabling the Postgres store or structured `response_format` output.

## Open Questions

All questions resolved during spec discussion.
