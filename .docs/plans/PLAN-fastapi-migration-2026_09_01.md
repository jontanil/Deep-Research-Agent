# FastAPI Migration + Config Externalization Implementation Plan

**Source:** SPEC — `.docs/specs/SPEC-fastapi-migration-2026_09_01.md`

**Goal:** Replace the Flask API layer with a FastAPI async `POST /research` endpoint preserving the exact `{content, references}` contract, and externalize all hardcoded runtime values (GCP project, Gemini models, credentials path, result/log paths, observability metadata) into `.env`-backed `AgentSettings`.

**Architecture:** The change is confined to the API and configuration layers; the supervisor-subagent research core is untouched except for the removal of a dead `store` parameter. FastAPI runs the agent's `ainvoke` natively async (no module-level event loop), Pydantic models define the wire format, `CORSMiddleware` replaces `CORS(app)`, and a global `Exception` handler reproduces the Flask 500 JSON contract. New pydantic-settings keys with defaults keep `.env` optional for the new values; the `.env` file and result output path are both anchored to the project root via a small `paths.py` helper.

**Tech Stack:** FastAPI, uvicorn (`[standard]`), pydantic-settings, Pydantic v2, pytest + httpx (TestClient) + pytest-cov, uv. Removes Flask, flask-cors, and the stray `flask-core` entry.

**Verification Source:** `.docs/specs/SPEC-fastapi-migration-2026_09_01.md` § Verification Plan (rows 1-9) + Implementation Decisions (result path, `.env` anchoring, CORS scope, dead-code cleanup, run command).

---

## Planning Notes / Verified Facts

- **No test suite or pytest config exists** (`glob` for `tests/**`, `pytest.ini`, `setup.cfg`, `conftest.py` returned nothing). This plan introduces the test harness.
- **FastAPI/uvicorn are NOT installed** in `.venv`; Flask/flask-cors/flask-core ARE (`pyproject.toml:10-12`). Dependency swap must precede all FastAPI work.
- **No `.env` file exists** in the repo. Confirmed in installed `pydantic_settings/sources/providers/dotenv.py:102` that a missing `env_file` is silently ignored (`if env_path.is_file()`), so tests can run without `.env`. Required fields `SERPAPI_API_KEY` / `POSTGRES_URL` must be supplied via `os.environ` in conftest.
- **`src/tools/ddg_mcp.py:15` runs `asyncio.run(_client.get_tools())` at import** (spawns `uvx duckduckgo-mcp-server`, requires `uvx` + network). Tests MUST stub `sys.modules["src.tools.ddg_mcp"]` (with `tools = []`) in conftest before any `src.agents.*` / `src.api.app` import.
- **ADC file at `src/application_default_credentials.json` is an INVALID placeholder** (all fields empty, `"type": ""`). `google.auth.load_credentials_from_file` raises `DefaultCredentialsError: The file ... does not have a valid type` at import (verified). Tests MUST patch `google.auth.load_credentials_from_file` in conftest (BEFORE any `src.*` import) to return a dummy credentials object; with that patch the real `llm_models` module imports and `create_model()`/`create_reasoning_model()` construct offline. The integration tests patch `app.deepagent` after import, so the real agent graph is only built at import (offline — verified `CompiledStateGraph`). See `BUG-adc-credentials-2026_09_01.md`.
- **`src/config/agent_configs.py:1` imports `langgraph.store.postgres` → `psycopg`, which fails on this machine** (`ImportError: no pq wrapper available ... libpq library not found`; the venv has pure-python psycopg with no binary wrapper). This blocks `import src.agents.research` for both the app and the tests. Task 1 adds `psycopg[binary]` to the dependency set (verified: with it, `from langgraph.store.postgres import PostgresStore` imports). The `make_store`/`make_backend` definitions stay (disabled feature), the import becomes loadable.
- **Loguru auto-creates parent dirs** for file sinks (`_file_sink.py:221-223` `_create_dirs`), so `logging.py` needs no explicit `mkdir` when switching to `settings.LOGS_DIR`.
- **`get_settings()` is `@lru_cache(maxsize=1)`** (`settings.py:25`). The FastAPI endpoint MUST call `get_settings()` at request time, and conftest MUST `cache_clear()` per test so `monkeypatch.setenv` overrides take effect.
- **TestClient must use `raise_server_exceptions=False`** so the Task 11 RED step (unhandled 500) returns a response body instead of re-raising into the test.
- `AgentSettings` requires `SERPAPI_API_KEY` and `POSTGRES_URL` with no defaults (`settings.py:17,20`); conftest supplies dummy values.

---

## Test File Organization

```
tests/
├── conftest.py                        # env vars, ddg_mcp stub, TestClient fixture
├── test_env_setup.py                  # smoke: env vars + ddg stub present
├── unit/
│   ├── config/
│   │   ├── test_paths.py              # mirrors src/config/paths.py
│   │   ├── test_settings.py           # mirrors src/config/settings.py
│   │   └── test_llm_models.py         # mirrors src/config/llm_models.py
│   ├── agents/
│   │   └── test_research.py           # mirrors src/agents/research.py (clean_output)
│   └── api/
│       └── test_schemas.py            # mirrors src/api/schemas.py
└── integration/
    ├── api/
    │   └── test_research.py           # mirrors src/api/app.py (contract, 400, 500, CORS, write)
    └── observability/
        └── test_logging.py            # mirrors src/observability/logging.py (LOGS_DIR)
```

---

## Task 1: Swap runtime dependencies (Flask → FastAPI/uvicorn) + lockfile

**Files:**
- Modify: `pyproject.toml:7-21` (`[project] dependencies`)
- Modify: `pyproject.toml` (add `[project.scripts]` entrypoint)
- Modify: `requirements.txt:9-10`
- Regenerate: `uv.lock`

**Verification Reference:** SPEC § Scope (dependency manifests) + Implementation Decisions › Run command & dependency pinning. Required before any FastAPI import.

**Risk:** Medium

**Depends on:** None

**Step 1: Edit `pyproject.toml` dependencies + build backend**

- Key change: remove `flask-core>=2.9.0` (line 10), `flask-cors>=6.0.2` (line 11), `flask[async]>=3.1.3` (line 12). Add `fastapi` and `uvicorn[standard]` to the `dependencies` list (keep `python-dotenv` — pydantic-settings needs it). Do NOT touch `langchain-openrouter` (out of scope).
- Add `psycopg[binary]` to the `dependencies` list — required so `src/config/agent_configs.py:1` can import (`langgraph.store.postgres` → `psycopg`; the pure-python wheel fails with `ImportError: no pq wrapper available` on this machine). Without it, `import src.agents.research` fails for both the app and the tests. Verified: with the binary wrapper, `from langgraph.store.postgres import PostgresStore` imports.
- Add a `[project.scripts]` table: `deepagent-api = "src.api.app:main"` (the `main()` will be added in Task 9; do not run the script yet).
- Add a `[build-system]` table so `uv sync` installs the project editable and generates the `deepagent-api` console script (verified: without a build backend, uv does not install the project and no script is produced):
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["src"]
  ```
  The `packages = ["src"]` line is required because the project name (`researchagent`) differs from the top-level package (`src`); hatchling auto-includes subpackages.

**Step 2: Edit `requirements.txt`**

- Key change: delete lines 9-10 (`flask[async]`, `flask-cors`); add `fastapi` and `uvicorn[standard]` (pin-free, matching pyproject).

**Step 3: Regenerate lockfile + sync venv**

Run: `uv lock; if ($?) { uv sync }`
Expected: lockfile updates with fastapi/uvicorn; flask/flask-cors/flask-core removed from the resolved set; the project itself is built and installed editable (`researchagent` dist-info appears in `.venv\Lib\site-packages`).

**Step 4: Verify**

Run: `uv run python -c "import fastapi, uvicorn, psycopg; print(fastapi.__version__, uvicorn.__version__)"`
Expected: prints two version numbers, no `ModuleNotFoundError` (psycopg imports too, proving the `agent_configs` chain is loadable).
Run: `uv run python -c "from importlib.metadata import distribution; print(distribution('researchagent').version)"`
Expected: prints `0.1.0` — the project is installed, so the `deepagent-api` console script exists (do not run it until Task 9 adds `main()`).

**Step 5: Commit**

```bash
git add pyproject.toml requirements.txt uv.lock
git commit -m "chore: swap Flask for FastAPI and uvicorn"
```

---

## Task 2: Test infrastructure (pytest, conftest with env + ddg stub)

**Files:**
- Modify: `pyproject.toml` (add `[dependency-groups] dev` + `[tool.pytest.ini_options]`)
- Create: `tests/conftest.py`
- Create: `tests/test_env_setup.py`

**Verification Reference:** Required by every TDD task in this plan. Addresses the AGENTS.md import-side-effect gotchas (required env vars, `uvx` spawn at `ddg_mcp` import, lru-cached settings).

**Risk:** Low

**Depends on:** Task 1

**Step 1: Add dev dependencies + pytest config to `pyproject.toml`**

- Key change: add `[dependency-groups]` with `dev = ["pytest>=8.3", "pytest-cov>=5", "httpx>=0.27"]`. Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["."]` (project root). `pythonpath` (pytest ≥7) inserts the project root into `sys.path` so `import src.*` works under `uv run pytest` even if the project is not installed — verified that without it, pytest cannot resolve `src` (`ModuleNotFoundError` at collection). Task 1's editable install makes it work too; this is belt-and-suspenders.

**Step 2: Create `tests/conftest.py`**

- Key change: at module top-level (BEFORE any `src.*` import), in order:
  1. `os.environ.setdefault("SERPAPI_API_KEY", "test-key")` and `os.environ.setdefault("POSTGRES_URL", "postgresql://localhost/test")` (required fields with no defaults). Also `os.environ.setdefault("USER_AGENT", "deepagent-test")` (silences the serpapi import warning).
  2. `os.environ.setdefault("LOGS_DIR", tempfile.mkdtemp(prefix="deepagent-test-logs-"))` — must be set before `src.observability.logging` is first imported (it captures settings at import, `logging.py:7-9`).
  3. Neutralize the invalid ADC file (`BUG-adc-credentials-2026_09_01.md`): `import google.auth; google.auth.load_credentials_from_file = lambda *a, **k: (object(), None)` BEFORE any `src.*` import — otherwise `src.config.llm_models` raises `DefaultCredentialsError` at import. Verified: with this patch the module imports and `create_model()`/`create_reasoning_model()` construct offline (a dummy `object()` credential is accepted by the `ChatGoogleGenerativeAI` constructor).
  4. Stub the import-time `uvx` spawn: build `types.ModuleType("src.tools.ddg_mcp")`, set `.tools = []`, insert into `sys.modules["src.tools.ddg_mcp"]`.
- Module-level constant `LOGS_TEST_DIR = Path(os.environ["LOGS_DIR"])` for Task 14 to assert against.
- Fixtures:
  - `clear_settings_cache` (autouse): calls `src.config.settings.get_settings.cache_clear()` before every test so `monkeypatch.setenv` works with the lru_cache (`settings.py:25`).
  - `client`: imports `src.api.app` as `app_module`, replaces `app_module.deepagent` with a fake async agent, returns `fastapi.testclient.TestClient(app_module.app, raise_server_exceptions=False)`. The fake must expose `async def ainvoke(self, input_state, config=None) -> {"messages": [object with `.content` = [{"text": <configured text>}]]}`. Real app import will build the graph once (offline); the patch redirects requests to the fake.

**Step 3: Create `tests/test_env_setup.py`**

- Test: `test_required_env_vars_are_set` asserts `os.environ["SERPAPI_API_KEY"] == "test-key"` and `os.environ["POSTGRES_URL"]`.
- Test: `test_ddg_mcp_is_stubbed` asserts `sys.modules["src.tools.ddg_mcp"].tools == []` (proves the `uvx` spawn workaround is active).

**Step 4: Verify**

Run: `uv sync; if ($?) { uv run pytest tests -q }`
Expected: `2 passed` in a few seconds — no `uvx` process spawned, no credential errors.

**Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests
git commit -m "test: add pytest harness with env and ddg_mcp import stubs"
```

---

## Task 3: `src/config/paths.py` — project-root anchoring helper

**Files:**
- Test: `tests/unit/config/test_paths.py`
- Implement: `src/config/paths.py` (new)

**Verification Plan Reference:** Success criterion "Report written to configured path" (Integration) + SPEC Implementation Decisions › Result file path behavior / `.env` file discovery. This helper is the shared mechanism for both anchorings.

**Risk:** Low

**Depends on:** Task 2

**Step 1: Write failing tests**

- Test: `tests/unit/config/test_paths.py::test_project_root_is_repo_root` — key assertion: `(project_root() / "pyproject.toml").exists()` and `(project_root() / "src").is_dir()`.
- Test: `tests/unit/config/test_paths.py::test_resolve_relative_anchors_to_project_root` — key assertion: `resolve_from_project_root("Result.md") == project_root() / "Result.md"`.
- Test: `tests/unit/config/test_paths.py::test_resolve_absolute_returned_unchanged` — passing an absolute path returns it unchanged.
- Test: `tests/unit/config/test_paths.py::test_resolve_is_cwd_independent` — `monkeypatch.chdir(tmp_path)` first, then `resolve_from_project_root("Result.md")` still equals `project_root() / "Result.md"`.
- Setup: no mocks; pure functions.

**Step 2: Run tests — expect RED**

Run: `uv run pytest tests/unit/config/test_paths.py -v`
Expected failure: `ModuleNotFoundError: No module named 'src.config.paths'`

**Step 3: Implement**

- Location: `src/config/paths.py`
- Key change: `project_root()` returns `Path(__file__).resolve().parent.parent.parent` (src/config/paths.py → config → src → repo root). `resolve_from_project_root(rel: str | Path) -> Path` returns `Path(rel)` unchanged if it is absolute, else `project_root() / rel`. Both are pure, CWD-independent.

**Step 4: Run tests — expect GREEN**

Run: `uv run pytest tests/unit/config/test_paths.py -v`
Expected: `4 passed`

**Step 5: Refactor**

No refactor needed — two tiny pure functions.

**Step 6: Commit**

```bash
git add src/config/paths.py tests/unit/config/test_paths.py
git commit -m "feat: add project-root path resolution helper"
```

---

## Task 4: Extend `AgentSettings` with externalized keys + anchored `.env`

**Files:**
- Test: `tests/unit/config/test_settings.py`
- Modify: `src/config/settings.py` (add fields, change `model_config`)

**Verification Plan Reference:** Success criterion "Model/project/credentials from config" (Unit) — settings defaults + env propagation. SPEC Components § 1.

**Risk:** Low

**Depends on:** Task 3 (settings imports `project_root` from `paths`)

**Step 1: Write failing tests**

- Test: `test_agent_settings_new_defaults` — instantiate `AgentSettings()` (required env supplied by conftest) and assert:
  - `GCP_PROJECT_ID == "catalan-dev-484209"`
  - `GEMINI_MODEL == "gemini-3-flash-preview"`
  - `GEMINI_REASONING_MODEL == "gemini-3-flash-preview"`
  - `GEMINI_CREDENTIALS_FILE == str(project_root() / "src/application_default_credentials.json")`
  - `RESULT_OUTPUT_PATH == "Result.md"`
  - `LOGS_DIR == "logs"`
  - `LANGFUSE_TAGS == ["deepagent"]` and `LANGFUSE_CALL_TYPE == "deepagent"`
  - Key precondition: `monkeypatch.delenv("LOGS_DIR", raising=False)` first. conftest sets the `LOGS_DIR` env var to a temp dir (for Task 14), and pydantic-settings gives env precedence over field defaults — without the `delenv`, `AgentSettings().LOGS_DIR` is the temp dir and this assertion can never pass.
- Test: `test_agent_settings_reads_env_override` — `monkeypatch.setenv("GEMINI_MODEL", "custom-model")`, then `get_settings.cache_clear()`; key assertion: `get_settings().GEMINI_MODEL == "custom-model"`.
- Setup: default pydantic-settings behavior; conftest autouse fixture clears the lru cache.

**Step 2: Run tests — expect RED**

Run: `uv run pytest tests/unit/config/test_settings.py -v`
Expected failure: `AttributeError: 'AgentSettings' object has no attribute 'GCP_PROJECT_ID'`

**Step 3: Implement**

- Location: `src/config/settings.py` → `AgentSettings`
- Key change: add the fields from SPEC Components § 1 with the defaults above. Use `GEMINI_CREDENTIALS_FILE: str = str(project_root() / "src/application_default_credentials.json")`. Set `LANGFUSE_TAGS: list[str] = ["deepagent"]`. Replace `model_config` `env_file=".env"` with `env_file=str(project_root() / ".env")` (anchored; missing file is silently ignored — verified `dotenv.py:102`), keep `extra='ignore'`.
- Reference: `from .paths import project_root` (same package).

**Step 4: Run tests — expect GREEN**

Run: `uv run pytest tests/unit/config/test_settings.py -v`
Expected: `2 passed`

**Step 5: Refactor**

No refactor needed — declarative field additions.

**Step 6: Commit**

```bash
git add src/config/settings.py tests/unit/config/test_settings.py
git commit -m "feat: externalize runtime values into AgentSettings"
```

---

## Task 5: Externalize GCP project / Gemini models / credentials in `llm_models.py`

**Files:**
- Test: `tests/unit/config/test_llm_models.py`
- Modify: `src/config/llm_models.py` (remove hardcoded `CREDENTIALS_FILE`/`PROJECT`/inline model names)

**Verification Plan Reference:** Success criterion "Model/project/credentials from config" (Unit). SPEC Components § 2.

**Risk:** Low

**Depends on:** Task 4

**Step 1: Write failing tests**

- Test: `test_create_model_uses_settings` — `monkeypatch.setattr(llm_models, "get_settings", lambda: FakeSettings(GEMINI_MODEL="custom-model", GCP_PROJECT_ID="custom-project"))` and `monkeypatch.setattr(llm_models, "ChatGoogleGenerativeAI", CapturingClass)` where `CapturingClass.__init__` records kwargs into a list. Call `llm_models.create_model()`. Key assertion: `captured["model"] == "custom-model"` and `captured["project"] == "custom-project"`.
- Test: `test_create_reasoning_model_uses_settings` — same patching with `GEMINI_REASONING_MODEL="custom-reasoning"`; call `create_reasoning_model("high")`. Key assertion: `captured["model"] == "custom-reasoning"` and `captured["thinking_level"] == "high"`.
- Test: `test_credentials_loaded_from_settings_path` — covers the "credentials from config" half of the SPEC criterion. Patch `google.auth.load_credentials_from_file` to record its filename argument and return `(object(), None)`; `monkeypatch.setattr(llm_models, "get_settings", lambda: FakeSettings(GCP_PROJECT_ID="p", GEMINI_MODEL="m", GEMINI_REASONING_MODEL="r", GEMINI_CREDENTIALS_FILE="custom-creds.json"))`; `importlib.reload(llm_models)`. Key assertion: the recorded path == `"custom-creds.json"` (the module-level credential load reads the settings value). Note: `importlib.reload` re-executes the module against the patched globals; the conftest `google.auth` patch keeps the file load non-crashing.
- Setup: `FakeSettings` is a plain object with the four needed attributes (`GCP_PROJECT_ID`, `GEMINI_MODEL`, `GEMINI_REASONING_MODEL`, `GEMINI_CREDENTIALS_FILE`). The real `llm_models` module is imported normally (the invalid ADC file is neutralized by conftest's `google.auth` patch — `BUG-adc-credentials-2026_09_01.md`); only the call-time `get_settings` global and the `ChatGoogleGenerativeAI` class are patched.
- Expected failure (RED): the captured `model` is the hardcoded `"gemini-3-flash-preview"` regardless of `FakeSettings`, so `assert captured["model"] == "custom-model"` fails (and, for the credentials test, the recorded path is the hardcoded `src/application_default_credentials.json`, so the `"custom-creds.json"` assertion fails).

**Step 2: Run tests — expect RED**

Run: `uv run pytest tests/unit/config/test_llm_models.py -v`
Expected failure: `AssertionError: assert 'gemini-3-flash-preview' == 'custom-model'`

**Step 3: Implement**

- Location: `src/config/llm_models.py`
- Key change: delete `CREDENTIALS_FILE` and `PROJECT` module constants and the inline model strings. Add `settings = get_settings()` at module level; load credentials from `settings.GEMINI_CREDENTIALS_FILE`. `create_model()` uses `model=settings.GEMINI_MODEL` with `thinking_level="minimal"`; `create_reasoning_model(reasoning_effort)` uses `model=settings.GEMINI_REASONING_MODEL` with `thinking_level=reasoning_effort`; both pass `project=settings.GCP_PROJECT_ID`, `credentials=credentials`, `temperature=0.0` (behavior preserved from `llm_models.py:28-43`).
- Reference: SPEC Components § 2 and `src/config/settings.py` fields from Task 4.

**Step 4: Run tests — expect GREEN**

Run: `uv run pytest tests/unit/config/test_llm_models.py -v`
Expected: `3 passed`

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/config/llm_models.py tests/unit/config/test_llm_models.py
git commit -m "feat: read GCP project, models, and credentials path from settings"
```

---

## Task 6: `clean_output` citation conversion (characterization/regression)

**Files:**
- Test: `tests/unit/agents/test_research.py`

**Verification Plan Reference:** Success criterion "`clean_output` citation conversion" (Unit) — `[[[Title — URL]]]` → `[1]`; dedup; numbering order.

**Risk:** Low

**Depends on:** Task 2 (imports `src.agents.research` under the conftest stubs; note this task runs BEFORE the dead-code cleanup in Task 7, so `research.py` still imports `response_model`/`make_backend` — both present at this point)

**Step 1: Write tests**

These are characterization tests for preserved behavior: `clean_output` already works, so they PASS on current code. They exist to guard the contract.

- Test: `test_clean_output_converts_citations_to_numbers` — input `"See [[[Alpha — https://a.com]]] and [[[Beta — https://b.com]]]"`. Key assertions: content contains `[1]` and `[2]` (in citation order), `references == {"Alpha — https://a.com": 1, "Beta — https://b.com": 2}`.
- Test: `test_clean_output_deduplicates_citations` — input uses the same citation marker twice. Key assertions: references has one entry with value `1`, both occurrences replaced with `[1]`.
- Test: `test_clean_output_no_citations_unchanged` — boundary: input `"plain text without any citation markers"`. Key assertions: content is unchanged and `references == {}`.
- Setup: none — pure function. Import via `from src.agents.research import clean_output`.

**Step 2: Run tests**

Run: `uv run pytest tests/unit/agents/test_research.py -v`
Expected: `3 passed` on the unchanged implementation (documented exception to red-first: this is a regression test for existing behavior, per SPEC "preserve the exact contract").

**Step 3: Refactor**

No refactor needed — `clean_output` (`research.py:56-72`) is already minimal.

**Step 4: Commit**

```bash
git add tests/unit/agents/test_research.py
git commit -m "test: characterize clean_output citation conversion"
```

---

## Task 7: Dead-code cleanup (`store` param, `make_store`/`make_backend` imports, `ResearchDocument`)

**Files:**
- Modify: `src/agents/research.py:8-9,16`
- Delete: `src/models/response_model.py`

**Verification Reference:** SPEC Implementation Decisions › References schema & dead-code cleanup (removes `store` from `create_research_agent`, drops unused `make_store`/`make_backend`/`ResearchDocument` imports). The signature change is required so Task 9's `create_research_agent(settings)` call works. Definitions in `src/config/agent_configs.py` remain (disabled feature).

**Risk:** Medium (import graph changes; app.py is temporarily broken until Task 9 rewrites it — nothing imports `src.api.app` between Tasks 7 and 9, so the test suite stays green)

**Depends on:** Task 6

**Step 1: Modify `src/agents/research.py`**

- Key change: change line 16 `def create_research_agent(settings, store):` → `def create_research_agent(settings):`. Remove line 8 `from ..config.agent_configs import make_backend, handle_tool_errors` → keep only `handle_tool_errors`. Remove line 9 `from ..models.response_model import ResearchDocument` and the commented-out `backend=make_backend` / `response_format= ToolStrategy(ResearchDocument)` lines (49, 51). Keep `# store=store` comment removal as well (line 50).

**Step 2: Delete `src/models/response_model.py`**

- Key change: remove the file and the now-empty `src/models/` directory (no `__init__.py` exists there).

**Step 3: Verify no dangling references**

Run:
```powershell
Select-String -Path "src\**\*.py" -Pattern "ResearchDocument|make_store|make_backend|response_model" -ErrorAction SilentlyContinue
```
Expected: matches only in `src/config/agent_configs.py` (the retained `make_store`/`make_backend` definitions). None in `app.py` or `research.py`.

**Step 4: Run full suite (should still pass)**

Run: `uv run pytest tests -q`
Expected: all tests green (no test imports `src.api.app` yet).

**Step 5: Commit**

```bash
git add src/agents/research.py src/models
git commit -m "refactor: remove dead store param and ResearchDocument model"
```

---

## Task 8: `src/api/schemas.py` — Pydantic request/response models

**Files:**
- Test: `tests/unit/api/test_schemas.py`
- Implement: `src/api/schemas.py` (new)

**Verification Plan Reference:** Success criterion "`POST /research` returns `{content, references}`" (E2E/Integration) — the wire contract is defined by these models. SPEC Components § 4 + Implementation Decisions › References schema.

**Risk:** Low

**Depends on:** Task 2

**Step 1: Write failing tests**

- Test: `test_research_request_defaults_query_to_empty` — key assertion: `ResearchRequest().query == ""`. (This default is what lets the endpoint translate a missing `query` key into the preserved 400 "No query found" instead of FastAPI's default 422 — see SPEC Constraints › error behavior.)
- Test: `test_research_request_accepts_query` — key assertion: `ResearchRequest(query="hello").query == "hello"`.
- Test: `test_research_response_references_is_dict_str_int` — key assertion: `ResearchResponse(content="c", references={"T — https://x": 1}).references == {"T — https://x": 1}` and its type is `dict[str, int]`.
- Test: `test_research_response_rejects_non_int_references` — key assertion: `ResearchResponse(content="c", references={"T": "x"})` raises `pydantic.ValidationError` (guards the wire contract against the old `List[str]` declaration).

**Step 2: Run tests — expect RED**

Run: `uv run pytest tests/unit/api/test_schemas.py -v`
Expected failure: `ModuleNotFoundError: No module named 'src.api.schemas'`

**Step 3: Implement**

- Location: `src/api/schemas.py`
- Key change: `class ResearchRequest(BaseModel): query: str = ""` and `class ResearchResponse(BaseModel): content: str; references: dict[str, int]` per SPEC Components § 4. Import from `pydantic`.

**Step 4: Run tests — expect GREEN**

Run: `uv run pytest tests/unit/api/test_schemas.py -v`
Expected: `4 passed`

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/api/schemas.py tests/unit/api/test_schemas.py
git commit -m "feat: add research request/response Pydantic schemas"
```

---

## Task 9: FastAPI app rewrite — happy path `POST /research` returns `{content, references}`

**Files:**
- Test: `tests/integration/api/test_research.py`
- Modify: `src/api/app.py` (full rewrite: remove Flask/event-loop, add FastAPI app + async endpoint)

**Verification Plan Reference:** Success criterion "`POST /research` returns `{content, references}`" (E2E/Integration). SPEC Components § 5, Data Flow.

**Risk:** High (whole-module rewrite; import side effects from `llm_models`, `logging`, `langfuse_config` at import; this is the first task that imports `src.api.app`)

**Depends on:** Tasks 1, 7, 8

**Step 1: Write failing test**

- Test: `tests/integration/api/test_research.py::test_research_returns_content_and_references` using the `client` fixture (fake `deepagent` with canned text containing `[[[Test Source — https://example.com]]]`).
- Behavior: POST `{"query": "test query"}` returns 200; body keys are exactly `{"content", "references"}`; `content` is `str` and contains the converted `[1]`; `references == {"Test Source — https://example.com": 1}` (proves `clean_output` ran in the real endpoint path).

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_returns_content_and_references -v`
Expected failure: `ModuleNotFoundError: No module named 'flask'` (Task 1 removed Flask; app.py still imports it).

**Step 3: Implement — minimal app for the happy path only**

- Location: `src/api/app.py` (rewrite)
- Key change:
  - Replace Flask imports with `from fastapi import FastAPI, HTTPException` and `from src.api.schemas import ResearchRequest, ResearchResponse`.
  - `app = FastAPI()`; `settings = get_settings()`; `deepagent = create_research_agent(settings)` (single call-site update per Task 7).
  - `@app.post("/research", response_model=ResearchResponse) async def research(payload: ResearchRequest)`:
    - Build `RunnableConfig` exactly as today (`app.py:44-51`) but metadata from settings: `{"call-type": settings.LANGFUSE_CALL_TYPE, "langfuse_tags": settings.LANGFUSE_TAGS}`.
    - `with propagate_attributes(session_id=f"deepagent-session-{uuid.uuid4()}"): result = await deepagent.ainvoke({"messages": [HumanMessage(payload.query)]}, config=config)` — NO module-level event loop, NO `run_until_complete`.
    - `response = result["messages"][-1].content[0]['text']`; `content, references = clean_output(response)`; `return ResearchResponse(content=content, references=references)`.
  - Drop unused imports: `flask_cors`, `queue`, `threading`, `json`, `AIMessageChunk`, `ToolMessage`, `make_store`.
  - Add the console-script entrypoint required by SPEC Implementation Decisions › Run command: `def main(): uvicorn.run("src.api.app:app")` (add `import uvicorn`). This is what Task 1's `[project.scripts] deepagent-api = "src.api.app:main"` and Task 16's `uv run deepagent-api` invoke; without it the documented run command fails with `AttributeError: no attribute 'main'`. `uvicorn.run` inserts the CWD (`app_dir="."` default), so it boots from the project root with or without the editable install.
- Do NOT yet add: the 400 empty-query check, the 500 exception handler, CORSMiddleware, or the result-file write — those are Tasks 10-13 red-green cycles.
- Reference: SPEC Components § 5, Data Flow; reuse `src/observability/logging.py` `logger`, `src/observability/langfuse_config.py` `langfuse_handler`, `src/agents/research.py` `create_research_agent`/`clean_output` unchanged.

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_returns_content_and_references -v`
Expected: PASS (a single run should take a few seconds; the real agent graph builds once at import, offline).

**Step 5: Refactor**

No refactor needed — this is the target structure.

**Step 6: Commit**

```bash
git add src/api/app.py tests/integration/api/test_research.py
git commit -m "feat: rewrite API as FastAPI with async research endpoint"
```

---

## Task 10: Empty/missing/blank query → 400 "No query found"

**Files:**
- Test: `tests/integration/api/test_research.py`
- Modify: `src/api/app.py` (validation in the endpoint)

**Verification Plan Reference:** Success criterion "Empty/missing query rejected" (Integration). SPEC Error Handling + Constraints › error behavior.

**Risk:** Low

**Depends on:** Task 9

**Step 1: Write failing test**

- Test: `test_research_rejects_empty_missing_or_blank_query` — `@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": "   "}])`. Key assertion for each: `response.status_code == 400` and `response.json()["detail"] == "No query found"` (match the Flask message `app.py:42`).

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_rejects_empty_missing_or_blank_query -v`
Expected failure: `assert 200 == 400` (fake agent still returns a valid result; no validation exists).

**Step 3: Implement**

- Location: `src/api/app.py` → `research()` top
- Key change: `if not payload.query.strip(): raise HTTPException(status_code=400, detail="No query found")` (the `query: str = ""` default from Task 8 makes a missing key land here too). Import `HTTPException` from `fastapi`.

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_rejects_empty_missing_or_blank_query -v`
Expected: PASS (3 parametrized cases).

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/api/app.py tests/integration/api/test_research.py
git commit -m "feat: reject empty query with 400"
```

---

## Task 11: Uncaught exception → 500 `{"status":"error","message":...}` JSON

**Files:**
- Test: `tests/integration/api/test_research.py`
- Modify: `src/api/app.py` (global exception handler)

**Verification Plan Reference:** Success criterion "Uncaught exception → 500 JSON" (Integration). SPEC Error Handling, Components § 5.

**Risk:** Low

**Depends on:** Task 9

**Step 1: Write failing test**

- Test: `test_uncaught_exception_returns_500_json` — patch `app.deepagent.ainvoke` (or the fake) to `side_effect=RuntimeError("boom")` via `monkeypatch`; POST a valid query.
- Key assertion: `response.status_code == 500` and `response.json() == {"status": "error", "message": "Internal server error"}` (mirror `app.py:29-34`).

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/api/test_research.py::test_uncaught_exception_returns_500_json -v`
Expected failure: response body is Starlette's plain-text `"Internal Server Error"` (the `client` fixture uses `raise_server_exceptions=False` so a 500 response is returned, not raised) — `assert {"status": "error", "message": "Internal server error"} == "Internal Server Error"` fails.

**Step 3: Implement**

- Location: `src/api/app.py`
- Key change: add `@app.exception_handler(Exception)` async handler that calls `logger.exception(str(exc))` and returns `JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})`. Import `JSONResponse` from `fastapi.responses`, `Request` from `fastapi`. Note: Starlette resolves the more specific `HTTPException` handler first (via MRO), so the 400 from Task 10 is NOT swallowed by this handler.
- Reference: SPEC Error Handling; reuse `src/observability/logging.py` `logger` (this is what Task 14's log assertion keys off).

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/api/test_research.py::test_uncaught_exception_returns_500_json -v`
Expected: PASS.

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/api/app.py tests/integration/api/test_research.py
git commit -m "feat: return 500 JSON on uncaught exceptions"
```

---

## Task 12: CORS enabled via `CORSMiddleware`

**Files:**
- Test: `tests/integration/api/test_research.py`
- Modify: `src/api/app.py` (middleware)

**Verification Plan Reference:** Success criterion "CORS enabled" (Integration contract). SPEC Implementation Decisions › CORS origins scope (allow all, no credentials — matches Flask `CORS(app)`).

**Risk:** Low

**Depends on:** Task 9

**Step 1: Write failing test**

- Test: `test_cors_preflight_allows_any_origin` — `client.options("/research", headers={"Origin": "http://example.com", "Access-Control-Request-Method": "POST"})`. Key assertions: `response.status_code == 200` and `response.headers["access-control-allow-origin"] == "*"`.

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/api/test_research.py::test_cors_preflight_allows_any_origin -v`
Expected failure: preflight returns `405 Method Not Allowed` with no `access-control-allow-origin` header → `assert "*" == None`-style failure.

**Step 3: Implement**

- Location: `src/api/app.py`
- Key change: add `app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])` right after `app = FastAPI()`. No new settings key (per spec decision). Import from `fastapi.middleware.cors`.

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/api/test_research.py::test_cors_preflight_allows_any_origin -v`
Expected: PASS.

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/api/app.py tests/integration/api/test_research.py
git commit -m "feat: enable CORS for all origins"
```

---

## Task 13: Report written to `RESULT_OUTPUT_PATH` (config-driven, parent auto-created)

**Files:**
- Test: `tests/integration/api/test_research.py`
- Modify: `src/api/app.py` (report write using `resolve_from_project_root`)

**Verification Plan Reference:** Success criterion "Report written to configured path" (Integration). SPEC Implementation Decisions › Result file path behavior (project-root anchor + auto-created parents).

**Risk:** Low

**Depends on:** Task 9 (uses Task 3's `resolve_from_project_root`)

**Step 1: Write failing test**

- Test: `test_research_writes_report_to_configured_path` — `monkeypatch.setenv("RESULT_OUTPUT_PATH", str(tmp_path / "reports" / "out.md"))` (absolute path, so nothing lands in the repo); POST a valid query containing a citation marker. Key assertions: `(tmp_path / "reports" / "out.md").exists()`, its text equals the cleaned content returned in the body (the `[1]`-converted markdown), and the `reports` parent was auto-created.

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_writes_report_to_configured_path -v`
Expected failure: `assert False` — no report file is written yet.

**Step 3: Implement**

- Location: `src/api/app.py` → `research()`
- Key change: before returning, resolve `out_path = resolve_from_project_root(settings.RESULT_OUTPUT_PATH)`; `out_path.parent.mkdir(parents=True, exist_ok=True)`; `out_path.write_text(content, encoding="utf-8")`. Call `get_settings()` inside the handler (Task 4 cache-clear fixture makes env overrides visible).
- Reference: `src/config/paths.py` from Task 3; replaces the hardcoded `open('Result.md', 'w', encoding='utf-8')` (`app.py:61`). Default `"Result.md"` → project root, preserving today's behavior.

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/api/test_research.py::test_research_writes_report_to_configured_path -v`
Expected: PASS.

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/api/app.py tests/integration/api/test_research.py
git commit -m "feat: write report to configurable, project-root-anchored path"
```

---

## Task 14: `LOGS_DIR` honored by `src/observability/logging.py`

**Files:**
- Test: `tests/integration/observability/test_logging.py`
- Modify: `src/observability/logging.py:7`

**Verification Plan Reference:** Success criterion "Logs directory configurable" (Integration). SPEC Components § 3.

**Risk:** Low

**Depends on:** Task 9 (imports the module; conftest sets `LOGS_DIR` before first import)

**Step 1: Write failing test**

- Test: `test_logs_written_to_configured_dir` — import `logger` from `src.observability.logging`, call `logger.error("synthetic log line")`, then key assertion: `any(LOGS_TEST_DIR.glob("*.log"))` (conftest's module-level temp dir). No mocks; real loguru sink.

**Step 2: Run test — expect RED**

Run: `uv run pytest tests/integration/observability/test_logging.py -v`
Expected failure: `assert []` / `assert False` — the sink is hardcoded to `logs/{date}.log` (`logging.py:7`), so the file is created in the repo `logs/` dir, not `LOGS_TEST_DIR`.

**Step 3: Implement**

- Location: `src/observability/logging.py:7`
- Key change: move `settings = get_settings()` (currently line 9) ABOVE the `log_file_name` assignment, then set `log_file_name = f'{settings.LOGS_DIR}/{now.strftime("%Y-%m-%d")}.log'` — line 7 currently executes before `settings` is defined, so referencing `settings` there would raise `NameError`. No `mkdir` needed — loguru auto-creates parents (`_file_sink.py:221-223`).

**Step 4: Run test — expect GREEN**

Run: `uv run pytest tests/integration/observability/test_logging.py -v`
Expected: PASS.

**Step 5: Refactor**

No refactor needed.

**Step 6: Commit**

```bash
git add src/observability/logging.py tests/integration/observability/test_logging.py
git commit -m "feat: honor LOGS_DIR setting for log output"
```

---

## Task 15: Update `README.md` and `.env.example`

**Files:**
- Modify: `README.md:83` (run command) and `README.md:144-145` (dependencies)
- Modify: `.env.example`

**Verification Reference:** SPEC Scope (README + .env.example) and Implementation Decisions › Run command & dependency pinning.

**Risk:** Low

**Depends on:** Task 1

**Step 1: Update `README.md:83`**

- Key change: replace `flask --app src/api/app run` with the new commands:
  ```bash
  uv run deepagent-api
  # or with reload during development:
  uv run uvicorn src.api.app:app --reload
  ```

**Step 2: Update `README.md:144-145`**

- Key change: replace the `flask[async]` / `flask-cors` dependency bullets with `fastapi` and `uvicorn[standard]`.

**Step 3: Update `.env.example`**

- Key change: add commented defaults for the new optional keys (keeping `.env` optional for them):
  ```
  GCP_PROJECT_ID=catalan-dev-484209
  GEMINI_CREDENTIALS_FILE=src/application_default_credentials.json
  GEMINI_MODEL=gemini-3-flash-preview
  GEMINI_REASONING_MODEL=gemini-3-flash-preview
  RESULT_OUTPUT_PATH=Result.md
  LOGS_DIR=logs
  LANGFUSE_TAGS=["deepagent"]
  LANGFUSE_CALL_TYPE=deepagent
  ```
- Leave existing keys (`SERPAPI_API_KEY`, `POSTGRES_URL`, research limits, langfuse, `LOGGING_LEVEL`) untouched.

**Step 4: Verify**

Run: `uv run python -c "from dotenv import dotenv_values; v=dotenv_values('.env.example'); assert 'GCP_PROJECT_ID' in v and 'RESULT_OUTPUT_PATH' in v; print('ok')"`
Expected: prints `ok` (README verification is a visual diff of lines 83 and 144-145).

**Step 5: Commit**

```bash
git add README.md .env.example
git commit -m "docs: update run command, dependencies, and env keys for FastAPI"
```

---

## Task 16: Manual E2E — app boots via uvicorn / `deepagent-api`

**Files:**
- None (manual verification; optionally re-check `README.md` run instructions)

**Verification Plan Reference:** Success criterion "App boots via uvicorn" (Manual/E2E). SPEC Verification Plan row 9.

**Risk:** Medium (manual; requires `.env` with `SERPAPI_API_KEY` + `POSTGRES_URL` and the ADC file — same requirement as today)

**Depends on:** Tasks 9, 15

**Step 1: Prepare**

- Ensure `.env` exists with `SERPAPI_API_KEY` and `POSTGRES_URL` populated (`cp .env.example .env` then fill), and `src/application_default_credentials.json` present.

**Step 2: Boot the server**

Run (from project root): `uv run deepagent-api`
Expected: uvicorn log line `Uvicorn running on http://0.0.0.0:8000`, no import-time errors (settings, llm_models, logging, ddg_mcp all load).

**Step 3: Verify `/docs` and contract**

- `Invoke-WebRequest http://localhost:8000/docs` → 200 (Swagger UI HTML).
- `Invoke-RestMethod -Method Post -Uri http://localhost:8000/research -ContentType "application/json" -Body '{"query":""}'` → 400 with `{"detail":"No query found"}`.
- Full happy path requires live Gemini credentials + network (acknowledged not-tested per SPEC); if credentials are available, POST a real query and confirm 200 with `{content, references}` and `Result.md` written at the repo root (default `RESULT_OUTPUT_PATH`).

**Step 4: Expected outcome**

- Server boots cleanly, `/docs` serves, empty query returns the preserved 400 JSON. Any `ModuleNotFoundError` or 500 on boot indicates a regression in the import chain or config resolution.

---

## Task 17: Coverage verification

**Files:**
- Modify (optional, only if the repo wants the gate persisted): `pyproject.toml` `[tool.coverage.run]` with `source = ["src"]`

**Verification Reference:** SPEC Verification Plan — full-suite regression gate over the migration surface.

**Risk:** Low

**Depends on:** Tasks 3-14

**Step 1: Run the full suite with coverage over the migration surface**

Run:
```
uv run pytest tests -q --cov=src/api --cov=src/config/settings.py --cov=src/config/llm_models.py --cov=src/config/paths.py --cov=src/observability --cov=src/agents/research.py --cov-report=term-missing --cov-fail-under=80
```
Expected: all tests PASS and total coverage ≥ 80%.

- Coverage scope rationale: `src/config` is targeted per-file to exclude unchanged `agent_configs.py` (dead Postgres store) and `prompts.py`; `src/api` includes `app.py` + `schemas.py`; `src/observability` includes `logging.py` (langfuse_config is stubbed in tests). `research.py` is largely covered via the app-import path + `clean_output` tests.
- If the gate lands just under 80 solely because of `app.main()` (the `uvicorn.run` body, not executed under TestClient), add a small test that calls `main()` with `monkeypatch`ed `uvicorn.run` instead of lowering the floor.

**Step 2: Red-flag sweep**

- Confirm no task left hardcoded values in the migration surface: `Select-String "catalan-dev|gemini-3-flash-preview|application_default_credentials" src\api,src\config,src\observability` should only match `settings.py` defaults (`.env.example` may also match, by design).
- Confirm `Result.md` / `logs/` are no longer written relative to CWD by the API layer (grep `app.py` for `open('Result.md'` → gone).

**Step 3: Commit (if gate was persisted to pyproject)**

```bash
git add pyproject.toml
git commit -m "test: enforce migration-surface coverage floor"
```

---

## Traceability

| SPEC success criterion | Test category | Level | Plan task |
|---|---|---|---|
| `POST /research` returns `{content, references}` | Functional correctness | E2E/Integration | Task 9 (integration), Task 8 (schemas unit) |
| Empty/missing query rejected | Error handling | Integration | Task 10 |
| Report written to configured path | Functional correctness | Integration | Task 13 (+ Task 3 paths unit) |
| `clean_output` citation conversion | Functional correctness | Unit | Task 6 |
| Model/project/credentials from config | Config correctness | Unit | Task 5 (model/project + credentials-path tests) + Task 4 settings unit |
| Logs directory configurable | Config correctness | Integration | Task 14 |
| CORS enabled | Integration contract | Integration | Task 12 |
| Uncaught exception → 500 JSON | Error handling | Integration | Task 11 |
| App boots via uvicorn | Deployment | Manual/E2E | Task 16 (`main()` from Task 9) |
| Deps manifests + console script | — | infra | Task 1 (build backend + `psycopg[binary]`) |
| Test harness / import-side-effect stubs | — | infra | Task 2 |
| Dead-code cleanup | — | infra | Task 7 |
| README + `.env.example` | — | infra | Task 15 |
| Coverage gate | — | — | Task 17 |

**Not tested (per SPEC § Not tested):** live LLM agent invocation (Task 16 optional), DDG MCP spawn, Postgres store.

---

## Red Flags Check

- **Large functions:** `research()` handler is a thin composition (~20 lines); no functions exceed 50 lines.
- **Deep nesting:** none introduced; endpoint bodies are linear.
- **Duplication:** project-root resolution lives only in `paths.py` (DRY); `clean_output` reused unchanged.
- **Missing error handling:** 400 (Task 10), 500 JSON (Task 11), tool-level errors remain in `handle_tool_errors` (unchanged).
- **Hardcoded values:** all externalized to `settings.py` defaults; verified in Task 17 sweep.
- **Tests for every testable behavior:** each of the 9 success criteria maps to ≥1 TDD/manual task; edge cases (missing/blank/empty query, absolute/relative result paths, CWD independence) are separate red-green cycles.
- **Import side effects:** ddg_mcp `asyncio.run` stub + invalid-ADC `google.auth` patch in conftest (Task 2); `psycopg` import fixed via `psycopg[binary]` dependency (Task 1); lru-cached settings handled by the autouse `cache_clear` fixture + request-time `get_settings()`.
- **Async/event-loop:** module-level loop and `run_until_complete` removed; `ainvoke` awaited natively (no idempotency concern — stateless POST, new thread_id per request).
- **BUG-specific concerns:** N/A (SPEC source).
