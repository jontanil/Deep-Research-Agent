from src.config.paths import project_root
from src.config.settings import AgentSettings, get_settings


def test_agent_settings_new_defaults(monkeypatch):
    monkeypatch.delenv("LOGS_DIR", raising=False)
    s = AgentSettings()
    assert s.GCP_PROJECT_ID == "catalan-dev-484209"
    assert s.GEMINI_MODEL == "gemini-3-flash-preview"
    assert s.GEMINI_REASONING_MODEL == "gemini-3-flash-preview"
    assert s.GEMINI_CREDENTIALS_FILE == str(
        project_root() / "src/application_default_credentials.json"
    )
    assert s.RESULT_OUTPUT_PATH == "Result.md"
    assert s.LOGS_DIR == "logs"
    assert s.LANGFUSE_TAGS == ["deepagent"]
    assert s.LANGFUSE_CALL_TYPE == "deepagent"


def test_agent_settings_reads_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    get_settings.cache_clear()
    assert get_settings().GEMINI_MODEL == "custom-model"