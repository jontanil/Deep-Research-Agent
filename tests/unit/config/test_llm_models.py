import importlib

import pytest


class FakeSettings:
    def __init__(self, **kwargs):
        self.GCP_PROJECT_ID = kwargs.get("GCP_PROJECT_ID", "project")
        self.GEMINI_MODEL = kwargs.get("GEMINI_MODEL", "model")
        self.GEMINI_REASONING_MODEL = kwargs.get("GEMINI_REASONING_MODEL", "reasoning")
        self.GEMINI_CREDENTIALS_FILE = kwargs.get("GEMINI_CREDENTIALS_FILE", "creds.json")


class CapturingClass:
    instances = []

    def __init__(self, **kwargs):
        CapturingClass.instances.append(kwargs)


def test_create_model_uses_settings(monkeypatch):
    from src.config import llm_models

    monkeypatch.setattr(
        llm_models, "get_settings", lambda: FakeSettings(GEMINI_MODEL="custom-model", GCP_PROJECT_ID="custom-project")
    )
    monkeypatch.setattr(llm_models, "ChatGoogleGenerativeAI", CapturingClass)
    CapturingClass.instances = []

    llm_models.create_model()

    assert CapturingClass.instances[0]["model"] == "custom-model"
    assert CapturingClass.instances[0]["project"] == "custom-project"


def test_create_reasoning_model_uses_settings(monkeypatch):
    from src.config import llm_models

    monkeypatch.setattr(
        llm_models, "get_settings", lambda: FakeSettings(GEMINI_REASONING_MODEL="custom-reasoning")
    )
    monkeypatch.setattr(llm_models, "ChatGoogleGenerativeAI", CapturingClass)
    CapturingClass.instances = []

    llm_models.create_reasoning_model("high")

    assert CapturingClass.instances[0]["model"] == "custom-reasoning"
    assert CapturingClass.instances[0]["thinking_level"] == "high"


def test_credentials_loaded_from_settings_path(monkeypatch):
    import google.auth

    from src.config import llm_models, settings as settings_module

    recorded = []

    def fake_load(path, *args, **kwargs):
        recorded.append(path)
        return (object(), None)

    monkeypatch.setattr(google.auth, "load_credentials_from_file", fake_load)
    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: FakeSettings(GEMINI_CREDENTIALS_FILE="custom-creds.json"),
    )

    importlib.reload(llm_models)

    assert recorded == ["custom-creds.json"]