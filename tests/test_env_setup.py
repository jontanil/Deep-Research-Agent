import os
import sys


def test_required_env_vars_are_set():
    assert os.environ["SERPAPI_API_KEY"] == "test-key"
    assert os.environ["POSTGRES_URL"]


def test_ddg_mcp_is_stubbed():
    assert sys.modules["src.tools.ddg_mcp"].tools == []
