import pytest
from pydantic import ValidationError

from src.api.schemas import ResearchRequest, ResearchResponse


def test_research_request_defaults_query_to_empty():
    assert ResearchRequest().query == ""


def test_research_request_accepts_query():
    assert ResearchRequest(query="hello").query == "hello"


def test_research_response_references_is_dict_str_int():
    resp = ResearchResponse(content="c", references={"T — https://x": 1})
    assert resp.references == {"T — https://x": 1}
    assert isinstance(resp.references, dict)


def test_research_response_rejects_non_int_references():
    with pytest.raises(ValidationError):
        ResearchResponse(content="c", references={"T": "x"})