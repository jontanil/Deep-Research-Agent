import uuid

from langchain_openai import ChatOpenAI

from .settings import get_settings

SESSION_ID = str(uuid.uuid4())

DEFAULT_HEADERS = {
    "x-opencode-session": SESSION_ID,
    "User-Agent": "deep-research-agent/1.0",
}


def create_reasoning_model(reasoning_effort: str):
    s = get_settings()
    return ChatOpenAI(
        model=s.OPENAI_REASONING_MODEL,
        base_url=s.OPENAI_BASE_URL,
        api_key=s.OPENAI_API_KEY,
        temperature=0.0,
        reasoning_effort=reasoning_effort,
        default_headers=DEFAULT_HEADERS,
    )


def create_model():
    s = get_settings()
    return ChatOpenAI(
        model=s.OPENAI_MODEL,
        base_url=s.OPENAI_BASE_URL,
        api_key=s.OPENAI_API_KEY,
        temperature=0.0,
        reasoning_effort="minimal",
        default_headers=DEFAULT_HEADERS,
    )
