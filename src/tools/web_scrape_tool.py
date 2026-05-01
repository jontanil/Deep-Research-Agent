from langchain_community.document_loaders import WebBaseLoader
from langchain.tools import tool, ToolException

from ..observability.logging import logger

@tool
def scrape_website(url: str) -> dict:
    """Scrape the text content of a webpage from a given URL."""
    try:
        logger.debug(f"Scraping url: {url}")
        loader = WebBaseLoader(
            url,
            header_template={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
            },
            requests_kwargs={"timeout": 30},
        )
        docs = loader.load()
        
        content = "\n".join([doc.page_content for doc in docs])
        
        return {
            "url": url,
            "content" : content[:4000]
        }
    
        # return content[:4000]  
    except Exception as e:
        logger.exception(f"Error scraping site: {url}")
        raise ToolException(str(e))