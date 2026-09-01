from functools import lru_cache

from pydantic_settings import BaseSettings,SettingsConfigDict

from .paths import project_root

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

    GCP_PROJECT_ID : str = "catalan-dev-484209"
    GEMINI_CREDENTIALS_FILE : str = str(project_root() / "src/application_default_credentials.json")
    GEMINI_MODEL : str = "gemini-3-flash-preview"
    GEMINI_REASONING_MODEL : str = "gemini-3-flash-preview"
    RESULT_OUTPUT_PATH : str = "Result.md"
    LOGS_DIR : str = "logs"
    LANGFUSE_TAGS : list[str] = ["deepagent"]
    LANGFUSE_CALL_TYPE : str = "deepagent"
    
    model_config = SettingsConfigDict(env_file=str(project_root() / ".env"), extra='ignore')


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings() 