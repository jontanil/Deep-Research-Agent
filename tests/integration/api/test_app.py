import pytest


def test_research_returns_content_and_references(client):
    resp = client.post("/research", json={"query": "test query"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"content", "references"}
    assert isinstance(body["content"], str)
    assert "[1]" in body["content"]
    assert body["references"] == {"Test Source — https://example.com": 1}


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": "   "}])
def test_research_rejects_empty_missing_or_blank_query(client, payload):
    resp = client.post("/research", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No query found"


def test_uncaught_exception_returns_500_json(client, monkeypatch):
    from src.api import app as app_module

    async def boom(input_state, config=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module.deepagent, "ainvoke", boom)
    resp = client.post("/research", json={"query": "test query"})
    assert resp.status_code == 500
    assert resp.json() == {"status": "error", "message": "Internal server error"}


def test_cors_preflight_allows_any_origin(client):
    resp = client.options(
        "/research",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"