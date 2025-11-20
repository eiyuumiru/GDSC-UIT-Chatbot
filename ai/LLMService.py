from __future__ import annotations
from typing import Any, Dict, List, Optional
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from .RetrieverService import ContextFormatter, RetrieverService, make_retrieve_tool
from .GroqService.GroqBase import GroqBase
from .config.Groq import GroqLLMConfig as cfg
from litellm.utils import trim_messages
from .Prompt.Prompts import SYSTEM_INSTRUCTIONS_MD, ANSWER_HUMAN_TEMPLATE_MD

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_INSTRUCTIONS_MD),
        ("human", ANSWER_HUMAN_TEMPLATE_MD),
    ]
)

def _collect_tool_chunks_from_state(state: MessagesState) -> List[Dict[str, Any]]:
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

def _get_last_user_question(state: MessagesState) -> str:
    for m in reversed(state["messages"]):
        if m.type == "human":
            return str(m.content or "")
    return ""

def _format_recent_history(state: MessagesState, max_chars: int = 2000, max_turns: int = 6) -> str:
    buf = []
    for m in state["messages"]:
        if m.type in ("human", "ai"):
            role = "Người dùng" if m.type == "human" else "Trợ lý"
            text = str(m.content or "").strip()
            if text:
                buf.append(f"{role}: {text}")
    if not buf:
        return ""
    tail = buf[-(max_turns*2):]
    joined = []
    total = 0
    for t in tail:
        if total + len(t) > max_chars:
            break
        joined.append(t)
        total += len(t)
    return "\n".join(joined)

class LLMService(ContextFormatter):
    def __init__(self, groq_api_key: str, model: str = cfg.DEFAULT_MODEL_NAME, temperature: float = cfg.DEFAULT_TEMPERATURE, timeout: float = cfg.DEFAULT_TIMEOUT, max_tokens: Optional[int] = None, retriever_config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.model = model
        groq_base = GroqBase()
        self.llm = groq_base.create_llm(api_key=groq_api_key, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout, max_retries=cfg.DEFAULT_MAX_RETRIES)
        self.memory = self.__init_Memory()
        self._retriever_service = RetrieverService(**(retriever_config or {}))
        self._retrieve_tool = make_retrieve_tool(self._retriever_service)
        self.graph = self.__init_Graph()

    def __init_Memory(self):
        return MemorySaver()
    
    def __query_or_response(self, state: MessagesState):
        planner_system = SystemMessage(
            content=(
                "Bạn là chatbot chuyên trả lời về chương trình đào tạo của trường UIT. "
                "Suy luận trong tâm trí: "
                "1. Câu hỏi này cần thông tin cụ thể nào? "
                "2. Lịch sử hội thoại có đủ ngữ cảnh không? "
                "3. Nếu cần dữ liệu chi tiết từ chương trình đào tạo, gọi 'retrieve'. "
                "4. Nếu có thể trả lời từ kiến thức chung, không cần gọi công cụ. "
                "Quyết định ngay, không giải thích quá trình."
            )
        )
        llm_with_tools = self.llm.bind_tools([self._retrieve_tool])
        response = llm_with_tools.invoke([planner_system] + state["messages"])
        return {"messages": [response]}
    
    def __generate_with_context(self, state: MessagesState):
        chunks = _collect_tool_chunks_from_state(state)
        contexts = self.format_context(chunks)
        history = _format_recent_history(state)
        messages = ANSWER_PROMPT.format_messages(question=_get_last_user_question(state), contexts=contexts, history=history)
        trimmed_result = trim_messages(messages=messages, model=self.model)
        messages = trimmed_result[0] if isinstance(trimmed_result, tuple) else trimmed_result
        out = self.llm.invoke(messages)
        return {"messages": [out]}

    def __init_Graph(self):
        tools = ToolNode([self._retrieve_tool])
        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("query_or_response", self.__query_or_response)
        graph_builder.add_node("tools", tools)
        graph_builder.add_node("generate_with_context", self.__generate_with_context)
        graph_builder.add_edge(START, "query_or_response")
        graph_builder.add_conditional_edges("query_or_response", tools_condition, {END: END, "tools": "tools"})
        graph_builder.add_edge("tools", "generate_with_context")
        graph_builder.add_edge("generate_with_context", END)
        return graph_builder.compile(checkpointer=self.memory)

    def __call__(self, question: str, thread_id: str = "default_session") -> Any:
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke({"messages": [HumanMessage(content=question)]}, config=config) # pyright: ignore[reportArgumentType]