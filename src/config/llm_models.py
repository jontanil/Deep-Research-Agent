# from langchain_openrouter import ChatOpenRouter 

# def create_reasoning_model(reasoning_effort: str):
#     return ChatOpenRouter(
#         model="openai/o3-mini",
#         reasoning={
#             "effort":reasoning_effort
#         }
#     )

# def create_model():
#     return ChatOpenRouter(
#         model="openai/gpt-4o-mini"
#     )

import google.auth
from langchain_google_genai import ChatGoogleGenerativeAI

from .settings import get_settings

settings = get_settings()

credentials, _ = google.auth.load_credentials_from_file(
    str(settings.GEMINI_CREDENTIALS_FILE),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

def create_reasoning_model(reasoning_effort: str):
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model= s.GEMINI_REASONING_MODEL,
        credentials= credentials,
        project= s.GCP_PROJECT_ID,
        temperature= 0.0,
        thinking_level=reasoning_effort
    )

def create_model():
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model= s.GEMINI_MODEL,
        credentials= credentials,
        project= s.GCP_PROJECT_ID,
        temperature= 0.0,
        thinking_level="minimal"
    )
