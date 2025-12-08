import os
from langchain_tavily import TavilySearch
from langchain_core.tools import tool, BaseTool
from typing import Dict, Any, List

class TavilyService:
    MAX_RESULTS = 5

    UIT_DOMAINS = [
        "daa.uit.edu.vn",
        "oep.uit.edu.vn",
        "tuyensinh.uit.edu.vn",
        "khtc.uit.edu.vn",
        "ctsv.uit.edu.vn",
        "uit.edu.vn",
        "sdh.uit.edu.vn",
        "thuvien.uit.edu.vn",
        "lib.uit.edu.vn",
        "diemthi.tuyensinh247.com",
        "facebook.com",
    ]

    def __init__(self):
        self.tavily_client = self.__init__tavily_client()

    def __init__tavily_client(self) -> TavilySearch:
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            raise ValueError("TAVILY_API_KEY not found in environment variables")
        try:
            return TavilySearch(
                api_key=api_key,
                max_results=self.MAX_RESULTS,
                include_domains=self.UIT_DOMAINS,  
                include_answer=False,              
                include_raw_content=False,         
                search_depth="advanced",           
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Tavily client: {e}")


    def search(self, query: str) -> tuple[str, List[Dict[str, Any]]]:
        try:
            raw = self.tavily_client.invoke({"query": query})
        except Exception as e:
            return (f"Lỗi Tavily search: {e}", [])

        results = raw.get("results", []) if isinstance(raw, dict) else raw
        if not results:
            return ("Không tìm thấy kết quả nào từ Tavily.", [])

        snippets: List[Dict[str, Any]] = []

        for item in results:
            url = item.get("url") or item.get("source") \
                or item.get("metadata", {}).get("source")
            content = item.get("content") or ""
            title = item.get("title") \
                or item.get("metadata", {}).get("title", "")
            if not url or not content:
                continue  

            metadata: Dict[str, Any] = item.get("metadata", {}) or {}
            metadata = dict(metadata)  # copy tránh sửa dữ liệu gốc
            metadata.update({"source": url, "title": title})

            snippets.append({
                "content": content,
                "metadata": metadata,
            })

        if not snippets:
            return ("Không tìm thấy kết quả nào từ Tavily.", [])

        summary_lines = [
            "Kết quả tìm kiếm từ website UIT:",
            *[f"- {s['metadata']['title'] or s['metadata']['source']} ({s['metadata']['source']})"
              for s in snippets],
        ]
        summary_text = "\n".join(summary_lines)

        return summary_text, snippets

def make_tavily_tool(svc: TavilyService) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def _tavily_search(query: str) -> tuple[str, List[Dict[str, Any]]]:
        """Search UIT knowledge base using Tavily."""
        # Implement the search logic here using svc
        return svc.search(query)
    return _tavily_search