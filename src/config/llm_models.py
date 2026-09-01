from langchain_openai import ChatOpenAI

from .settings import get_settings


def create_reasoning_model(reasoning_effort: str):
    s = get_settings()
    return ChatOpenAI(
        model=s.OPENAI_REASONING_MODEL,
        base_url=s.OPENAI_BASE_URL,
        api_key=s.OPENAI_API_KEY,
        temperature=0.0,
        reasoning_effort=reasoning_effort,
    )


def create_model():
    s = get_settings()
    return ChatOpenAI(
        model=s.OPENAI_MODEL,
        base_url=s.OPENAI_BASE_URL,
        api_key=s.OPENAI_API_KEY,
        temperature=0.0,
        reasoning_effort="minimal",
    )
