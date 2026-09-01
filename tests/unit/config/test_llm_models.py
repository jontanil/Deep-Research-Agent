class FakeSettings:
    def __init__(self, **kwargs):
        self.OPENAI_API_KEY = kwargs.get("OPENAI_API_KEY", "key")
        self.OPENAI_BASE_URL = kwargs.get("OPENAI_BASE_URL", "https://example.com/v1")
        self.OPENAI_MODEL = kwargs.get("OPENAI_MODEL", "model")
        self.OPENAI_REASONING_MODEL = kwargs.get("OPENAI_REASONING_MODEL", "reasoning")


class CapturingClass:
    instances = []

    def __init__(self, **kwargs):
        CapturingClass.instances.append(kwargs)


def test_create_model_uses_settings(monkeypatch):
    from src.config import llm_models

    monkeypatch.setattr(
        llm_models, "get_settings", lambda: FakeSettings(OPENAI_MODEL="custom-model")
    )
    monkeypatch.setattr(llm_models, "ChatOpenAI", CapturingClass)
    CapturingClass.instances = []

    llm_models.create_model()

    assert CapturingClass.instances[0]["model"] == "custom-model"
    assert CapturingClass.instances[0]["base_url"] == "https://example.com/v1"
    assert CapturingClass.instances[0]["reasoning_effort"] == "minimal"


def test_create_reasoning_model_uses_settings(monkeypatch):
    from src.config import llm_models

    monkeypatch.setattr(
        llm_models, "get_settings", lambda: FakeSettings(OPENAI_REASONING_MODEL="custom-reasoning")
    )
    monkeypatch.setattr(llm_models, "ChatOpenAI", CapturingClass)
    CapturingClass.instances = []

    llm_models.create_reasoning_model("high")

    assert CapturingClass.instances[0]["model"] == "custom-reasoning"
    assert CapturingClass.instances[0]["reasoning_effort"] == "high"
