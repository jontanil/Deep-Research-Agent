from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, ModelCallLimitMiddleware
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from deepagents import CompiledSubAgent

from ..config import prompts
from ..config.llm_models import create_model
from ..observability.langfuse_config import langfuse_handler 
from ..tools.google_search_tool import search_google
from ..tools.web_scrape_tool import scrape_website 
from ..tools.ddg_mcp import tools

def get_custom_middleware(model_call_limit: int, tool_call_limit: int):
    return [# ModelCallLimitMiddleware(run_limit=model_call_limit, exit_behavior='end'),
            ToolCallLimitMiddleware(run_limit=tool_call_limit, exit_behavior='continue')]

def create_collector_agent(sub_agent_model, custom_middleware, recursion_limit):
    tools.append(scrape_website)
    tools.append(search_google)
    # tools = [search_google,scrape_website]

    data_collector_graph = create_agent(
        model= sub_agent_model,
        tools= tools,
        system_prompt= prompts.COLLECTOR_PROMPT,
        middleware= custom_middleware,
        checkpointer=MemorySaver()
    )

    async def collector_runnable(input_state, config=None):
        cfg = {
            **(config or {}), 
            "recursionLimit": recursion_limit, 
            "max_concurrency": 3,
            "callbacks": [langfuse_handler],
            "metadata":{
                "call-type":"subagent",
                "langfuse_tags":["subagent","data-collector"]
            }
        }
        invoke_fn = getattr(data_collector_graph, "ainvoke", None) or getattr(data_collector_graph, "invoke")
        try:
            return await invoke_fn(input_state, cfg)
        except GraphRecursionError:
            return {"error": "recursion_limit_reached", "limit": cfg["recursionLimit"]}

    return CompiledSubAgent(
        name="data-collector",
        description="Specialized agent for collecting concise data",
        runnable=data_collector_graph,
    )

def create_validator_agent(sub_agent_model, custom_middleware, recursion_limit):
    tools.append(scrape_website)
    tools.append(search_google)
    # tools = [search_google,scrape_website]
    
    validator_graph = create_agent(
        model = sub_agent_model,
        tools= tools,
        system_prompt= prompts.VALIDATOR_PROMPT,
        middleware= custom_middleware,
        checkpointer= MemorySaver() 
    )

    async def validator_runnable(input_state, config=None):
        cfg = {
            **(config or {}), 
            "recursionLimit": recursion_limit, 
            "max_concurrency": 3,
            "callbacks": [langfuse_handler],
            "metadata":{
                "call-type":"subagent",
                "langfuse_tags":["subagent","data-validator"]
            }
        }
        invoke_fn = getattr(validator_graph, "ainvoke", None) or getattr(validator_graph, "invoke")
        try:
            return await invoke_fn(input_state, cfg)
        except GraphRecursionError:
            return {"error": "recursion_limit_reached", "limit": cfg["recursionLimit"]}

    return CompiledSubAgent(
        name="data-validator",
        description="Specialized agent for validating data",
        runnable=validator_graph
    )

def create_visualizer_agent(sub_agent_model, custom_middleware, recursion_limit):
    tools.append(scrape_website)
    tools.append(search_google)
    # tools = [search_google,scrape_website]
    
    visualizer_graph = create_agent(
        model = sub_agent_model,
        tools= tools,
        system_prompt= prompts.VISUALIZER_PROMPT,
        middleware= custom_middleware,
        checkpointer= MemorySaver() 
    )

    async def visualizer_runnable(input_state, config=None):
        cfg = {
            **(config or {}), 
            "recursionLimit": recursion_limit, 
            "max_concurrency": 3,
            "callbacks": [langfuse_handler],
            "metadata":{
                "call-type":"subagent",
                "langfuse_tags":["subagent","data-visualizer"]
            }
        }
        invoke_fn = getattr(visualizer_graph, "ainvoke", None) or getattr(visualizer_graph, "invoke")
        try:
            return await invoke_fn(input_state, cfg)
        except GraphRecursionError:
            return {"error": "recursion_limit_reached", "limit": cfg["recursionLimit"]}

    return CompiledSubAgent(
        name="data-visualizer",
        description="Specialized agent for visualizing data",
        runnable=visualizer_graph
    )