from langgraph.store.postgres import PostgresStore
from deepagents.backends import StoreBackend, StateBackend, CompositeBackend
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from langchain_core.tools import ToolException

def make_backend(runtime):
            return CompositeBackend(
                default=StateBackend(runtime),  # ephemeral per-thread state
                routes={"/memories/": StoreBackend(runtime)}  # persistent route
            )

def make_store(settings):
    store_ctx = PostgresStore.from_conn_string(settings.POSTGRES_URL)
    store = store_ctx.__enter__()          
    store.setup() 
    return store

@wrap_tool_call
async def handle_tool_errors(request, handler):
    """Catch ToolException and let the agent continue."""
    try:
        return await handler(request) 
    except ToolException as e:
        return ToolMessage(
            content=f"Tool '{request.tool_call['name']}' is unavailable: {str(e)}. Using other tools to answer.",
            tool_call_id=request.tool_call["id"],
            status="error"
        )
    except Exception as e:
        return ToolMessage(
            content=f"Unexpected error in tool '{request.tool_call['name']}': {str(e)}.",
            tool_call_id=request.tool_call["id"],
            status="error"
        ) 
