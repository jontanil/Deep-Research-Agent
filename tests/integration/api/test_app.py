def test_research_returns_content_and_references(client):
    resp = client.post("/research", json={"query": "test query"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"content", "references"}
    assert isinstance(body["content"], str)
    assert "[1]" in body["content"]
    assert body["references"] == {"Test Source — https://example.com": 1}