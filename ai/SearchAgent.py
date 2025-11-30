import os
import logging
from typing import Any, Dict, List, Tuple
import requests
from dotenv import load_dotenv
from .QueryGeneratorLLM import generate_queries_llm

# logging + Load biến mt

logger = logging.getLogger(__name__)

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
assert TAVILY_API_KEY, "Thiếu TAVILY_API_KEY! Vui lòng thêm vào file .env"

TAVILY_URL = "https://api.tavily.com/search"

# subdomain UIT lấy deeplink chuẩn

UIT_DOMAINS: List[str] = [
    "www.uit.edu.vn",
    "tuyensinh.uit.edu.vn",
    "oep.uit.edu.vn",
    "daa.uit.edu.vn",
    "ctsv.uit.edu.vn",
    "forum.uit.edu.vn",
    "courses.uit.edu.vn",
    "thuvien.uit.edu.vn",
    "lib.uit.edu.vn",
    "khtc.uit.edu.vn",
    "sdh.uit.edu.vn",
]

# search_tavily (low-level client)

def search_tavily(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Gọi Tavily để tìm kiếm thông tin trong các domain UIT."""

    payload: Dict[str, Any] = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "include_domains": UIT_DOMAINS,
        "include_raw_content": True,
    }

    try:
        response = requests.post(TAVILY_URL, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        logger.debug("[TAVILY] Query='%s' -> %d results", query, len(results))
        return results
    except requests.RequestException as e:
        logger.error("[TAVILY ERROR] %s", e)
        return []

# search_uit + format kết quả

def search_uit(query: str, max_results: int = 5) -> Tuple[List[Dict[str, Any]], str]:
    """Hàm tiện dụng dành cho các module khác."""
    results = search_tavily(query, max_results=max_results)
    formatted = format_results_text(results)
    return results, formatted


def format_results_text(
    results: List[Dict[str, Any]],
    max_snippet_len: int = 300,
) -> str:
    """Định dạng list kết quả Tavily thành 1 chuỗi text gọn gàng."""
    if not results:
        return "Không tìm thấy kết quả nào từ các trang UIT.\n"

    lines: List[str] = [f"Tổng số kết quả: {len(results)}\n"]
    for i, r in enumerate(results, start=1):
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        snippet = r.get("snippet") or r.get("content") or ""
        snippet = snippet.replace("\n", " ")

        if len(snippet) > max_snippet_len:
            snippet = snippet[:max_snippet_len] + "..."

        lines.append(f"[{i}] {title}")
        lines.append(f"    URL: {url}")
        lines.append(f"    Nội dung: {snippet}\n")

    return "\n".join(lines)

# Agent cấp cao: dùng LLM sinh query -> Tavily -> context

def run_web_search_agent(
    question: str,
    max_queries: int = 3,
    max_results_per_query: int = 3,
) -> Dict[str, Any]:
    """Agent nhiều bước: LLM sinh query -> Tavily -> gộp kết quả."""

    question = (question or "").strip()
    if not question:
        return {
            "queries": [],
            "results": [],
            "context": "Không có câu hỏi để tìm kiếm.",
        }

    # Dùng LLM sinh query
    queries: List[str] = generate_queries_llm(question, max_queries=max_queries) or []
    queries = [q.strip() for q in queries if q and q.strip()]
    logger.debug("[WEB_SEARCH_AGENT] Question='%s' -> queries=%s", question, queries)

    if not queries:
        return {
            "queries": [],
            "results": [],
            "context": "LLM không sinh được truy vấn tìm kiếm phù hợp.",
        }

    # Gọi Tavily cho từng query
    all_results: List[Dict[str, Any]] = []
    seen_urls = set()

    for q in queries:
        results, _ = search_uit(q, max_results=max_results_per_query)
        for r in results:
            url = r.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    # Định dạng thành context text (debug / test)
    context_text = format_results_text(all_results, max_snippet_len=400)

    return {
        "queries": queries,
        "results": all_results,
        "context": context_text,
    }

# Helper: chuyển kết quả thành chunks cho RAG

def web_search_chunks(
    question: str,
    max_queries: int = 3,
    max_results_per_query: int = 3,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Chạy web search và trả về (context_text, chunks cho RAG)."""

    agent_out = run_web_search_agent(
        question=question,
        max_queries=max_queries,
        max_results_per_query=max_results_per_query,
    )

    results: List[Dict[str, Any]] = agent_out.get("results", []) or []
    context_text: str = agent_out.get("context") or ""

    chunks: List[Dict[str, Any]] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        snippet = (r.get("snippet") or r.get("content") or "").replace("\n", " ")

        # Ghi URL sâu trực tiếp vào content
        if title and url:
            content = f"{title}\nNguồn: {url}\n\n{snippet}".strip()
        elif url:
            content = f"Nguồn: {url}\n\n{snippet}".strip()
        else:
            content = (title or snippet).strip()

        chunks.append(
            {
                "source": url,
                "content": content,
                "metadata": {
                    "source": url,
                    "title": title,
                    "type": "web_search",
                    "provider": "tavily",
                },
            }
        )

    return context_text, chunks

# test nhanh 

if __name__ == "__main__":
    print("=== Test Tavily Search cho UIT (low-level) ===")
    q = input("Nhập câu query muốn tìm (Enter để bỏ qua test low-level): ").strip()

    if q:
        results, text = search_uit(q, max_results=3)
        print("\n===== KẾT QUẢ ĐỊNH DẠNG (search_uit) =====")
        print(text)

    print("\n=== Test Web Search Agent (LLM + Tavily) ===")
    q2 = input("Nhập câu hỏi của sinh viên UIT: ").strip()
    if q2:
        agent_out = run_web_search_agent(q2)
        print("\n>>> Queries LLM sinh ra:")
        for idx, qq in enumerate(agent_out.get("queries", []), start=1):
            print(f"  {idx}. {qq}")

        print("\n===== CONTEXT TEXT (đưa cho LLM chính) =====")
        print(agent_out.get("context", ""))
