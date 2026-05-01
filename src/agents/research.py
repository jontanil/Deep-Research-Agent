import re
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents.structured_output import ToolStrategy

from ..config import prompts
from ..config.llm_models import create_reasoning_model, create_model
from ..config.agent_configs import make_backend, handle_tool_errors
from ..models.response_model import ResearchDocument
from ..observability.logging import logger
from ..tools.google_search_tool import search_google
from ..tools.web_scrape_tool import scrape_website
from ..tools.ddg_mcp import tools
from .subagents import get_custom_middleware, create_collector_agent, create_validator_agent, create_visualizer_agent
        
def create_research_agent(settings, store):
    try:

        if settings.DEEP_RESEARCH == 1:
            reasoning = settings.DEEP_RESEARCH_REASONING_EFFORT
            model_call_limit = settings.DEEP_RESEARCH_MODEL_CALL_LIMIT
            tool_call_limit = settings.DEEP_RESEARCH_TOOL_CALL_LIMIT
            recursion_limit = settings.DEEP_RESEARCH_RECURSION_LIMIT
        else:
            reasoning = settings.QUICK_RESEARCH_REASONING_EFFORT
            model_call_limit = settings.QUICK_RESEARCH_MODEL_CALL_LIMIT
            tool_call_limit = settings.QUICK_RESEARCH_TOOL_CALL_LIMIT
            recursion_limit = settings.QUICK_RESEARCH_RECURSION_LIMIT

        model = create_reasoning_model(reasoning_effort=reasoning)
        sub_agent_model = create_model()
        custom_middleware = get_custom_middleware(model_call_limit, tool_call_limit)

        data_collector_subagent = create_collector_agent(sub_agent_model, custom_middleware,recursion_limit)
        data_validator_subagent = create_validator_agent(sub_agent_model, custom_middleware,recursion_limit)
        data_visualizer_subagent = create_visualizer_agent(sub_agent_model, custom_middleware,recursion_limit)

        # tools = [search_google,scrape_website]
        tools.append(search_google)
        tools.append(scrape_website)       
        
        return create_deep_agent(
            model= model,
            tools = tools,
            subagents = [data_collector_subagent, data_validator_subagent, data_visualizer_subagent],
            system_prompt= prompts.RESEARCH_PROMPT,
            checkpointer=MemorySaver(),
            middleware=[handle_tool_errors],
            # backend=make_backend,
            # store=store,
            # response_format= ToolStrategy(ResearchDocument)
        )
    except Exception as e:
        logger.exception(str(e))

def clean_output(content: str) -> tuple[str,dict]:

    pattern = r"\[\[\[(.*?)\]\]\]" 
    matches = re.findall(pattern, content)
    
    result: dict = {}
    counter = 1
    
    for match in matches:
        if match not in result:
            result[match] = counter
            counter += 1

    for key, value in result.items():
        content = content.replace(f"[[[{key}]]]", f"[{value}]")

    return content, result

    

    
