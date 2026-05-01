import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

_client = MultiServerMCPClient(
    {
        "duckduckgo": {
            "command": "uvx",
            "args": ["duckduckgo-mcp-server"],
            "transport": "stdio",
        }
    }
)

tools = asyncio.run(_client.get_tools())