from src.config.settings import AgentSettings, get_settings


def test_agent_settings_new_defaults(monkeypatch):
    monkeypatch.delenv("LOGS_DIR", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    s = AgentSettings(_env_file=None)
    assert s.OPENAI_BASE_URL == "https://api.openai.com/v1"
    assert s.OPENAI_MODEL == "gpt-4o-mini"
    assert s.OPENAI_REASONING_MODEL == "gpt-4o"
    assert s.RESULT_OUTPUT_PATH == "Result.md"
    assert s.LOGS_DIR == "logs"
    assert s.LANGFUSE_TAGS == ["deepagent"]
    assert s.LANGFUSE_CALL_TYPE == "deepagent"


def test_agent_settings_reads_env_override(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "custom-model")
    get_settings.cache_clear()
    assert get_settings().OPENAI_MODEL == "custom-model"
