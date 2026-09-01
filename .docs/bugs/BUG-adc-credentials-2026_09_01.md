# BUG: Invalid ADC credentials file crashes `llm_models` import and app startup

## Summary

`src/application_default_credentials.json` is an empty placeholder (every field blank, including `"type": ""`). `src/config/llm_models.py` loads it unconditionally at module import via `google.auth.load_credentials_from_file`, which rejects the empty `type` and raises `DefaultCredentialsError`. As a result `import src.config.llm_models` — and therefore `import src.api.app` — always fails, so the API cannot start and any test that imports the agent/config chain fails at collection. This will also block the upcoming model-provider diversification work because credential loading is hardcoded to GCP and coupled to import time.

## Expected Behavior

- Importing `src.config.llm_models` (and the app) succeeds, loading valid Google credentials from the configured ADC path.
- If the credentials file is missing or malformed, the app fails fast with a clear, actionable error message identifying the path and the problem — not a cryptic auth exception at import.
- Credential loading should be decoupled from module import so adding other model providers later does not inherit this failure mode.

## Actual Behavior

`google.auth.load_credentials_from_file` raises `DefaultCredentialsError: The file ... does not have a valid type. Type is , expected one of ('authorized_user', 'service_account', 'external_account', 'external_account_authorized_user', 'impersonated_service_account', 'gdch_service_account')`. Because the call happens at module import (`llm_models.py:23-26`), any import of the research/app code path crashes immediately.

## Symptoms

- `flask --app src/api/app run` (current run command) fails at import; server never boots.
- `import src.api.app` / `import src.agents.research` raises `DefaultCredentialsError`.
- Every test that imports `src.config.llm_models`, `src.agents.*`, or `src.api.app` errors at collection with this exception.
- No user-facing or actionable message about the broken credentials file.

## Environment

- **Language/Runtime**: Python 3.13
- **Framework**: LangGraph/deepagents + Flask (currently), Google Gemini via `langchain_google_genai`
- **OS**: Windows
- **Other**: `google-auth` (installed); ADC file at `src/application_default_credentials.json` (149 bytes, all fields empty)

## Steps to Reproduce

1. From the repo root, run the credentials loader exactly as `llm_models.py` does:
   `uv run python -c "import google.auth; google.auth.load_credentials_from_file(r'src/application_default_credentials.json', scopes=['https://www.googleapis.com/auth/cloud-platform'])"`
2. Observe `DefaultCredentialsError` instead of a loaded credentials object.
3. Alternatively, `uv run python -c "import src.config.llm_models"` — same exception at module import.

Expected: credentials load; actual: exception raised at import, blocking the app and all dependent imports.

## Root Cause Analysis

### Causal Chain

[Commit/edits left `src/application_default_credentials.json` as an empty template] → [llm_models.py imports it unconditionally at module import] → [google-auth validates the `type` field and rejects the empty value] → [`DefaultCredentialsError` raised during import] → [app cannot start; dependent imports and tests fail]

### Root Cause

The checked-in ADC file is a placeholder whose `type` field is empty (`"type": ""`). `google.auth._default._load_credentials_from_info` requires `type` to be one of `authorized_user` / `service_account` / `external_account` / `external_account_authorized_user` / `impersonated_service_account` / `gdch_service_account`. The empty value fails validation, and since `llm_models.py` performs the load at module top-level with no try/except, the exception propagates to every importer. The defect is twofold: (1) an invalid credentials file is present where a valid one is required, and (2) the code has no validation, no graceful degradation, and no clear error — it hard-crashes at import.

### Contributing Factors

- **Import-time side effects**: `llm_models.py:23-26` runs network-adjacent auth setup at module load; nothing is lazy.
- **Hardcoded, GCP-specific path**: `CREDENTIALS_FILE = Path(__file__).parent.parent / "application_default_credentials.json"` (`llm_models.py:20`) couples the module to one fixed file and provider.
- **No configurable path today**: the path cannot be pointed at a valid file without code changes (the FastAPI migration's `GEMINI_CREDENTIALS_FILE` setting will fix this).
- **Silent placeholder**: the invalid file looks like a valid one; only at import does it explode with a low-level auth error.

### Evidence

- `src/application_default_credentials.json` — all fields empty, `"type": ""` (verified by reading the file).
- `src/config/llm_models.py:20-26` — `CREDENTIALS_FILE` + module-level `load_credentials_from_file(...)` with no error handling.
- Reproduced error (this session): `google.auth.exceptions.DefaultCredentialsError: The file D:\...\src\application_default_credentials.json does not have a valid type. Type is , expected one of (...)`. Full traceback in Appendix.

### Confidence and Unknowns

- **Confidence**: High — the failure reproduces directly from the file contents and the exact code path.
- **Unknowns**: When/how the file was emptied (no git-blame of the file was performed). Whether a valid ADC file exists elsewhere on the machine.

## Classification

- **Severity**: High — the API cannot start and the entire test/import chain is broken until fixed or worked around.
- **Impact Scope**: All runtime and test usage of the research agent / API; blocks the FastAPI migration tests and the upcoming model-provider diversification.
- **Regression**: Unknown — no recent-commit analysis performed; the file appears to be a committed placeholder.
- **Reproducibility**: Always.

## Suggested Fix

### Approach

Two-part fix:

1. **Operational**: place a valid ADC JSON (service-account or authorized-user format) at `src/application_default_credentials.json`, or — once the FastAPI migration lands — point the configurable `GEMINI_CREDENTIALS_FILE` setting at a valid file. This unblocks startup immediately.
2. **Structural (aligns with model-provider diversification)**: make credential loading lazy, configurable, and provider-agnostic:
   - Resolve the credentials path from settings (`GEMINI_CREDENTIALS_FILE`) instead of a hardcoded relative path.
   - Do not perform network/auth work at module import; load credentials on first use (lazy), or guard the import-time load with explicit validation.
   - When the configured file is missing or invalid, raise a clear, actionable error naming the path and listing the accepted credential `type` values, instead of the raw `DefaultCredentialsError`.
   - Keep the loading behind a provider-specific adapter so adding another model provider (OpenAI, Anthropic, etc.) does not inherit GCP/ADC assumptions.

The FastAPI migration plan (`.docs/plans/PLAN-fastapi-migration-2026_09_01.md`) already adds a **test-time workaround** — conftest patches `google.auth.load_credentials_from_file` to return a dummy credentials object before any `src.*` import. That unblocks tests, but it is a workaround: the production bug (invalid file → no boot) remains until this fix lands.

### Alternative Approaches

- Commit a real (non-secret) development ADC file — only acceptable if it contains no live secrets; risk of leaking credentials.
- Add `psycopg`-style validation at startup in `main()` before serving traffic, giving a clear error instead of an import crash — handles symptom but not the hardcoded/provider-coupling root cause.
- Fully stub `src.config.llm_models` in tests instead of patching google-auth — moves the divergence further from reality; the conftest patch is preferred because it keeps the real module under test.

### Post-Fix Verification

- `import src.config.llm_models` succeeds with a valid credentials file; `create_model()`/`create_reasoning_model()` construct without error.
- `import src.api.app` succeeds and the server boots (via `uv run deepagent-api` or `uv run uvicorn src.api.app:app`).
- With a missing or malformed file, startup fails with a clear message naming the configured path and expected `type` values — not a raw auth exception.
- No hardcoded `"catalan-dev-484209"` / `"gemini-3-flash-preview"` / `src/application_default_credentials.json` assumptions remain in the credential-loading path.
- Tests that stub credentials (conftest google-auth patch) still pass unchanged.
- Provider-agnostic adapter: adding a second provider does not require touching GCP-specific import-time code.

## User Observations

- The repo's `AGENTS.md` documents the ADC file as required and the app as runnable, so the placeholder state is likely an accidental blanking rather than intentional.
- Model-provider diversification is planned next; the current GCP-only, import-time credential loading is a structural obstacle to that work.

## Appendix

Reproduced traceback (this session):

```
File "<string>", line 1, in <module>
  import google.auth; c,_=google.auth.load_credentials_from_file(
      r'...\src\application_default_credentials.json',
      scopes=['https://www.googleapis.com/auth/cloud-platform'])
File "...\google\auth\_default.py", line 191, in load_credentials_from_file
  return _load_credentials_from_info(filename, info, scopes, default_scopes, quota_project_id, request)
File "...\google\auth\_default.py", line 290, in _load_credentials_from_info
  raise exceptions.DefaultCredentialsError(...)
google.auth.exceptions.DefaultCredentialsError: The file ...\src\application_default_credentials.json does not
have a valid type. Type is , expected one of ('authorized_user', 'service_account', 'external_account',
'external_account_authorized_user', 'impersonated_service_account', 'gdch_service_account').
```

`src/application_default_credentials.json` content (149 bytes):

```json
{
  "account": "",
  "client_id": "",
  "client_secret": "",
  "quota_project_id": "",
  "refresh_token": "",
  "type": "",
  "universe_domain": ""
}
```