import os
from serpapi import GoogleSearch
from langchain.tools import tool, ToolException

from ..config.settings import get_settings
from ..observability.logging import logger

@tool()
def search_google(search_term: str):
    """
    Search google for anything    
    """
    try:
        settings = get_settings()

        params = {
            "api_key": settings.SERPAPI_API_KEY,
            "engine": "google",
            "q": search_term,
            # "location": "Austin, Texas, United States",
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en"
        }
        logger.debug(f"Searching google for: {search_term}")
        search = GoogleSearch(params)
        search_json = search.get_json()
        # logger.debug(f"search JSON: {search_json}")

        if search_json.get("error") is not None:
            raise ToolException(search_json["error"])
        
        organic_results = search_json.get("organic_results")

        return organic_results
    
    except Exception as e:
        logger.exception(str(e))
        raise ToolException(f"Error: {str(e)}")
