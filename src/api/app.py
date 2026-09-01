import uuid

from fastapi import FastAPI, HTTPException
from langfuse import propagate_attributes
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agents.research import create_research_agent, clean_output
from src.api.schemas import ResearchRequest, ResearchResponse
from src.config.settings import get_settings
from src.observability.langfuse_config import langfuse_handler
from src.observability.logging import logger

app = FastAPI()

settings = get_settings()
deepagent = create_research_agent(settings)


@app.post("/research", response_model=ResearchResponse)
async def research(payload: ResearchRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="No query found")

    config: RunnableConfig = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "callbacks": [langfuse_handler],
        "metadata": {
            "call-type": settings.LANGFUSE_CALL_TYPE,
            "langfuse_tags": settings.LANGFUSE_TAGS,
        },
    }

    with propagate_attributes(session_id=f"deepagent-session-{uuid.uuid4()}"):
        result = await deepagent.ainvoke(
            {"messages": [HumanMessage(payload.query)]}, config=config
        )

    response = result["messages"][-1].content[0]["text"]
    content, references = clean_output(response)
    return ResearchResponse(content=content, references=references)


def main():
    import uvicorn

    uvicorn.run("src.api.app:app")
