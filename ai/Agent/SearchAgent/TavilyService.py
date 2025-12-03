import os
from langchain_tavily import TavilySearch
from langchain_core.tools import tool, BaseTool
from typing import Dict, Any, List

class TavilyService:
    MAX_RESULTS = 5

    def __init__(self):
        self.tavily_client = self.__init__tavily_client()

    def __init__tavily_client(self) -> TavilySearch:
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not found in environment variables")
        try:
            return TavilySearch(api_key=api_key, max_results=self.MAX_RESULTS)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Tavily client: {e}")


    def search(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        # TODO: Implement actual search logic
        return ("No results found", [])

def make_tavily_tool(svc: TavilyService) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def _tavily_search(query: str) -> tuple[str, List[Dict[str, Any]]]:
        """Search UIT knowledge base using Tavily."""
        # Implement the search logic here using svc
        return svc.search(query)
    return _tavily_search