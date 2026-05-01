import uuid,sys, asyncio, threading, queue, json
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, request, abort, jsonify, Response
from flask_cors import CORS
from langfuse import propagate_attributes
from langchain_core.messages import HumanMessage, AIMessageChunk, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agents.research import create_research_agent, clean_output
from src.config.settings import get_settings
from src.config.agent_configs import make_store
from src.observability.langfuse_config import langfuse_handler
from src.observability.logging import logger

app = Flask(__name__)
CORS(app) 

settings = get_settings()
# store = make_store(settings)
deepagent = create_research_agent(settings, "store")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "status": "error",
        "message": "Internal server error"
    }), 500

@app.post('/research')
def retrieve():
    try:
        body = request.get_json(silent=True) or {}
        query = body.get('query', '')
        if query == '':
            abort(400, description="No query found") 

        config: RunnableConfig = {
            "configurable": {"thread_id": str(uuid.uuid4())},
            "callbacks": [langfuse_handler],
            "metadata":{
                "call-type":"deepagent",
                "langfuse_tags":["deepagent"]
            }
        }

        async def run_agent():
            with propagate_attributes(session_id=f"deepagent-session-{uuid.uuid4()}"):
                return await deepagent.ainvoke({"messages": [HumanMessage(query)]}, config=config)

        result = loop.run_until_complete(run_agent())
        response = result["messages"][-1].content[0]['text']

        content, references = clean_output(response)
        with open('Result.md', 'w', encoding= 'utf-8') as f:
            f.write(content)

        return jsonify({"content": content, "references": references})
    except Exception as e:
        logger.exception(str(e))
        raise

