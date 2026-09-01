import os
import sys
import types
import tempfile
from pathlib import Path

os.environ.setdefault("SERPAPI_API_KEY", "test-key")
os.environ.setdefault("POSTGRES_URL", "postgresql://localhost/test")
os.environ.setdefault("USER_AGENT", "deepagent-test")
os.environ.setdefault("LOGS_DIR", tempfile.mkdtemp(prefix="deepagent-test-logs-"))

_ddg_stub = types.ModuleType("src.tools.ddg_mcp")
_ddg_stub.tools = []
sys.modules["src.tools.ddg_mcp"] = _ddg_stub

LOGS_TEST_DIR = Path(os.environ["LOGS_DIR"])

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield


@pytest.fixture
def client():
    from src.api import app as app_module
    from fastapi.testclient import TestClient

    class FakeAgent:
        def __init__(self, text="[[[Test Source — https://example.com]]]"):
            self.text = text

        async def ainvoke(self, input_state, config=None):
            message = types.SimpleNamespace()
            message.content = [{"text": self.text}]
            return {"messages": [message]}

    app_module.deepagent = FakeAgent()
    return TestClient(app_module.app, raise_server_exceptions=False)
