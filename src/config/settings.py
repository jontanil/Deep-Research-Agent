from functools import lru_cache

from pydantic_settings import BaseSettings,SettingsConfigDict

class AgentSettings(BaseSettings):
    DEEP_RESEARCH_RECURSION_LIMIT : int = 100
    DEEP_RESEARCH_REASONING_EFFORT : str = "high"
    DEEP_RESEARCH_TOOL_CALL_LIMIT : int = 10
    DEEP_RESEARCH_MODEL_CALL_LIMIT : int = 10

    QUICK_RESEARCH_RECURSION_LIMIT : int = 10
    QUICK_RESEARCH_REASONING_EFFORT : str = "low"
    QUICK_RESEARCH_TOOL_CALL_LIMIT : int = 3
    QUICK_RESEARCH_MODEL_CALL_LIMIT : int = 5
    DEEP_RESEARCH : int = 0

    SERPAPI_API_KEY : str
    LOGGING_LEVEL : str = "DEBUG"
    
    POSTGRES_URL : str
    
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings() 