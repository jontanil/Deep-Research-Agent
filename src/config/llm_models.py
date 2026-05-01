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

from pathlib import Path
import google.auth
from langchain_google_genai import ChatGoogleGenerativeAI

CREDENTIALS_FILE = Path(__file__).parent.parent / "application_default_credentials.json"
PROJECT = "catalan-dev-484209"

credentials, _ = google.auth.load_credentials_from_file(
    str(CREDENTIALS_FILE),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

def create_reasoning_model(reasoning_effort: str):
    return ChatGoogleGenerativeAI(
        model= "gemini-3-flash-preview",
        credentials= credentials,
        project= PROJECT,
        temperature= 0.0,
        thinking_level=reasoning_effort
    )

def create_model():
    return ChatGoogleGenerativeAI(
        model= "gemini-3-flash-preview",
        credentials= credentials,
        project= PROJECT,
        temperature= 0.0,
        thinking_level="minimal"
    )
