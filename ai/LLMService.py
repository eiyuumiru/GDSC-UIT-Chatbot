from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from .Agent.SearchAgent.TavilyService import TavilyService, make_tavily_tool
from .RetrieverService.RetrieverService import (
    RetrieverService,
    make_retrieve_tool,
)
from .GroqService.GroqBase import GroqBase
from .config.Groq import GroqLLMConfig as cfg
from litellm.utils import trim_messages
from .Prompt.Prompts import PLANNER_ROUTER_PROMPT
from .Prompt import (
    ANSWER_PROMPT,
    SMALL_TALK_ANSWER_PROMPT,
    GURADRAIL_ANSWER_PROMPT,
    ADVISOR_PROMPT,
    ADVISOR_RENDER_PROMPT,
    ADVISOR_CLASSIFIER_MSG_PROMPT,
)

class AppState(MessagesState):
    route: Optional[str]
    advisor_mode: Optional[bool]
    advisor_result: Optional[Dict[str, Any]]
    advisor_clarify_pending: Optional[bool]

def _collect_tool_chunks_from_state(state: AppState) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for msg in reversed(state["messages"]):
        if getattr(msg, "type", None) != "tool":
            break
        artifact = getattr(msg, "artifact", [])
        if isinstance(artifact, list):
            for c in artifact:
                content = c.get("content", "").strip()
                if content:
                    chunks.append(c)
    return chunks[::-1]

def _get_last_user_question(state: AppState) -> str:
    for m in reversed(state["messages"]):
        if m.type == "human":
            return str(m.content or "")
    return ""

def _get_recent_conversation(state: AppState, max_pairs: int = 2) -> List[Any]:
    """Lấy N cặp hội thoại gần nhất (human + ai), bỏ qua ToolMessage"""
    recent_messages = []
    human_count = 0
    
    for msg in reversed(state["messages"]):
        if msg.type in ("human", "ai"):
            recent_messages.insert(0, msg)
            if msg.type == "human":
                human_count += 1
                if human_count >= max_pairs:
                    break
    
    return recent_messages

def _format_recent_history(
    state: AppState, max_chars: int = 2000, max_turns: int = 6
) -> str:
    buf = []
    for m in state["messages"]:
        if m.type in ("human", "ai"):
            role = "Người dùng" if m.type == "human" else "Trợ lý"
            text = str(m.content or "").strip()
            if text:
                buf.append(f"{role}: {text}")
    if not buf:
        return ""
    tail = buf[-(max_turns * 2) :]
    joined: List[str] = []
    total = 0
    for t in tail:
        if total + len(t) > max_chars:
            break
        joined.append(t)
        total += len(t)
    return "\n".join(joined)


def _safe_text(val: Any) -> str:
    """Escape braces to avoid .format issues and ensure string type."""
    text = str(val or "")
    return text.replace("{", "{{").replace("}", "}}")

def _has_tool_calls(state: AppState) -> bool:
    msgs = state.get("messages") or []
    if not msgs:
        return False
    last = msgs[-1]
    tool_calls = getattr(last, "tool_calls", None)
    return bool(tool_calls)


class LLMService():
    def __init__(
        self,
        groq_api_key: str,
        model: str = cfg.DEFAULT_MODEL_NAME,
        temperature: float = cfg.DEFAULT_TEMPERATURE,
        timeout: float = cfg.DEFAULT_TIMEOUT,
        max_tokens: Optional[int] = None,
        retriever_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.model = model
        groq_base = GroqBase()
        self.llm = groq_base.create_llm(
            api_key=groq_api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=cfg.DEFAULT_MAX_RETRIES,
        )
        self.memory = self.__init_Memory()
        self._retriever_service = RetrieverService(**(retriever_config or {}))
        self._search_agent_service = TavilyService()
        self._tavily_tool = make_tavily_tool(self._search_agent_service)
        self._retrieve_tool = make_retrieve_tool(self._retriever_service)
        self.graph = self.__init_Graph()

    def __invoke_text_only(self, messages):
        """Invoke LLM with tool_choice disabled to avoid accidental tool calls."""
        llm_no_tools = self.llm.with_config({"extra_body": {"tool_choice": "none"}})
        return llm_no_tools.invoke(messages)

    def __init_Memory(self):
        return MemorySaver()

    def __guardrail(self, state: AppState):
        question = _get_last_user_question(state)
        messages = GURADRAIL_ANSWER_PROMPT.format_messages(
            question=question,
            user_query=question,
        )
        response = self.llm.invoke(messages)
        classification = str(response.content or "").strip().upper()
        if "NEED_ADVISOR_INFO" in classification:
            return {"route": "advisor"}
        if "NEED_GENERAL_INFO" in classification:
            return {"route": "general"}
        return {"route": "small_talk"}
    
    def __should_use_advisor(self, state: AppState) -> bool:
        """Dùng LLM phân loại intent tư vấn ngành dựa trên lượt hiện tại + lịch sử ngắn."""
        question = _get_last_user_question(state)
        if not question or not str(question).strip():
            return False
        history = _format_recent_history(state, max_chars=1200, max_turns=2)
        messages = ADVISOR_CLASSIFIER_MSG_PROMPT.format_messages(
            history=history or "(trống)",
            question=question,
        )
        try:
            res = self.__invoke_text_only(messages)
            label = str(res.content or "").strip().upper()
            if "ADVISOR" in label:
                return True
            if "GENERAL" in label or "NO" in label:
                return False
        except Exception:
            return False
        return False

    def __planner(self, state: AppState):
        """Planner (LLM Agent): Quyết định tools nào cần dùng (parallel calling)"""
        planner_system = SystemMessage(content=PLANNER_ROUTER_PROMPT)
        recent_messages = _get_recent_conversation(state, max_pairs=2)

        llm_with_tools = self.llm.bind_tools(
            [self._retrieve_tool, self._tavily_tool],
            parallel_tool_calls=True 
        )
        response = llm_with_tools.invoke([planner_system] + recent_messages)
        return {"messages": [response]}
    
    def __generator(self, state: AppState):
        """Generator: Gen câu trả lời cuối cùng từ LLM (có/không context)"""
        question = _get_last_user_question(state)
        route = state.get("route")
                
        if route == "small_talk":
            messages = SMALL_TALK_ANSWER_PROMPT.format_messages(question=question)
            trimmed = trim_messages(messages=messages, model=self.model)
            messages = trimmed[0] if isinstance(trimmed, tuple) else trimmed
            out = self.llm.invoke(messages)
            return {"messages": [out]}
        
        # RAG flow: Sử dụng context từ tools và 2 cặp hội thoại gần nhất
        contexts = _collect_tool_chunks_from_state(state)
        recent_messages = _get_recent_conversation(state, max_pairs=2)
        
        # Format history từ recent messages
        history_parts = []
        for msg in recent_messages:
            if msg.type == "human":
                history_parts.append(f"Người dùng: {msg.content}")
            elif msg.type == "ai" and msg.content:
                history_parts.append(f"Trợ lý: {msg.content}")
        history = "\n".join(history_parts)
                
        messages = ANSWER_PROMPT.format_messages(
            question=question,
            contexts=contexts,
            history=history,
        )

        # Count tokens in contexts
        # contexts_text = "\n".join([chunk.get("content", "") for chunk in contexts])
        # contexts_tokens = token_counter(model=self.model, text=contexts_text)
        # print(f"📦 Contexts: {len(contexts)} chunks, {contexts_tokens:,} tokens")
        # print(f"📜 History: {len(history)} characters")
        # print(f"History: {history}")
        trimmed = trim_messages(messages=messages, model=self.model)
        messages = trimmed[0] if isinstance(trimmed, tuple) else trimmed
        out = self.llm.invoke(messages)

        # input_tokens = token_counter(model=self.model, messages=messages)
        # output_tokens = token_counter(model=self.model, text=str(out.content or ""))
        # print(f"🤖 Final Response: {input_tokens:,} input + {output_tokens:,} output = {input_tokens + output_tokens:,} tokens")

        return {"messages": [out]}

    def __advisor(self, state: AppState):
        """Advisor node: sinh khuyến nghị ngành dựa trên question + context từ tools."""
        question = _get_last_user_question(state)
        contexts = _collect_tool_chunks_from_state(state)
        context_text = "\n\n".join(
            [c.get("content", "") for c in contexts if c.get("content")]
        )
        # Escape braces để tránh lỗi format khi context chứa JSON
        context_text_safe = context_text.replace("{", "{{").replace("}", "}}")

        messages = ADVISOR_PROMPT.format_messages(
            question=question,
            contexts=context_text_safe or "Không có dữ liệu context.",
        )
        out = self.__invoke_text_only(messages)

        advisor_result: Optional[Dict[str, Any]] = None
        clarify_pending = False
        try:
            parsed = json.loads(str(out.content))
            if isinstance(parsed, dict):
                advisor_result = parsed
                major = str(parsed.get("major", "") or "").strip()
                if not major:
                    clarify_pending = True
        except Exception:
            advisor_result = None

        return {"messages": [out], "advisor_result": advisor_result, "advisor_clarify_pending": clarify_pending}

    def __generator_advisor(self, state: AppState):
        """Trình bày kết quả tư vấn ngành."""
        advisor = state.get("advisor_result") or {}
        question = _get_last_user_question(state)

        def _as_list(value: Any) -> List[str]:
            if isinstance(value, list):
                return [str(x).strip() for x in value if str(x).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        major = ""
        reasons = []
        cautions = []
        next_steps = []
        if isinstance(advisor, dict):
            major = str(advisor.get("major", "") or "").strip()
            reasons = _as_list(advisor.get("reasons"))
            cautions = _as_list(advisor.get("cautions"))
            next_steps = _as_list(advisor.get("next_steps"))

        major_lower = major.lower()
        major_unavailable = any(
            phrase in major_lower
            for phrase in ["không phù hợp", "khong phu hop", "không đào tạo", "khong dao tao", "không có ngành", "khong co nganh"]
        )

        has_major = bool(major) and not major_unavailable

        messages = ADVISOR_RENDER_PROMPT.format_messages(
            question=_safe_text(question),
            major=_safe_text(major),
            reasons=_safe_text("\n".join(reasons) if reasons else ""),
            cautions=_safe_text("\n".join(cautions) if cautions else ""),
            next_steps=_safe_text("\n".join(next_steps) if next_steps else ""),
            major_unavailable=str(major_unavailable),
        )

        out = self.__invoke_text_only(messages)
        return {"messages": [out]}

    def __route_after_guardrail(self, state: AppState) -> str:
        """Routing function: quyết định flow sau Guardrail"""
        route = state.get("route", "general")
        if route == "small_talk":
            return "generator"
        if route == "advisor":
            return "advisor"
        return "planner" 

    def __route_after_planner(self, state: AppState) -> str:
        """Routing sau planner: ưu tiên tools nếu có tool_calls, nếu không có thì generator."""
        if _has_tool_calls(state):
            return "tools"
        return "generator"

    def __route_after_tools(self, state: AppState) -> str:
        """Routing sau ToolNode: chọn generator thường."""
        return "generator"

    def __init_Graph(self):
        tools = ToolNode([self._retrieve_tool, self._tavily_tool])
        
        graph_builder = StateGraph(AppState)
        graph_builder.add_node("guardrail", self.__guardrail)
        graph_builder.add_node("planner", self.__planner)
        graph_builder.add_node("tools", tools)
        graph_builder.add_node("generator", self.__generator)
        graph_builder.add_node("advisor", self.__advisor)
        graph_builder.add_node("generator_advisor", self.__generator_advisor)

        graph_builder.add_edge(START, "guardrail")
        graph_builder.add_conditional_edges("guardrail", self.__route_after_guardrail,
            {
                "planner": "planner",
                "generator": "generator",
                "advisor": "advisor",
            },
        )
        graph_builder.add_conditional_edges(
            "planner",
            self.__route_after_planner,
            {
                "tools": "tools",
                "generator": "generator",
            },
        )
        graph_builder.add_conditional_edges(
            "tools",
            self.__route_after_tools,
            {
                "generator": "generator",
            },
        )
        graph_builder.add_edge("advisor", "generator_advisor")
        graph_builder.add_edge("generator_advisor", END)
        graph_builder.add_edge("generator", END)
        return graph_builder.compile(checkpointer=self.memory)

    def __call__(self, question: str, thread_id: str = "default_session") -> Any:
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=question)]}, config=config # type: ignore
        )
        return result

    def reset_memory(self, thread_id: str = "default_session") -> None:
        """Xoá memory cho một thread cụ thể"""
        self.memory.delete_thread(thread_id)