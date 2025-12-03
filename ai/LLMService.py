from __future__ import annotations
from typing import Any, Dict, List, Optional
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode, tools_condition
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
from .Prompt import ANSWER_PROMPT, SMALL_TALK_ANSWER_PROMPT, GURADRAIL_ANSWER_PROMPT

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

def _format_recent_history(
    state: MessagesState, max_chars: int = 2000, max_turns: int = 6
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

    def __init_Memory(self):
        return MemorySaver()

    def __guardrail(self, state: MessagesState):
        question = _get_last_user_question(state)
        messages = GURADRAIL_ANSWER_PROMPT.format_messages(
            question=question,
        )
        response = self.llm.invoke(messages)
        classification = str(response.content or "").strip().upper()
        
        if "NEEDS_INFO" in classification:
            return {"messages": [], "route": "needs_info"}
        else: return {"messages": [], "route": "small_talk"}
    
    def __planner(self, state: MessagesState):
        """Planner (LLM Agent): Quyết định tools nào cần dùng (parallel calling)"""
        planner_system = SystemMessage(
            content=(PLANNER_ROUTER_PROMPT)
        )
        llm_with_tools = self.llm.bind_tools(
            [self._retrieve_tool, self._tavily_tool],
            parallel_tool_calls=True 
        )
        response = llm_with_tools.invoke([planner_system] + state["messages"])
        return {"messages": [response]}
    
    def __generator(self, state: MessagesState):
        """Generator: Gen câu trả lời cuối cùng từ LLM (có/không context)"""
        question = _get_last_user_question(state)
                
        if not state.get("route") == "needs_info":
            messages = SMALL_TALK_ANSWER_PROMPT.format_messages(
                question=question,
            )
            trimmed = trim_messages(messages=messages, model=self.model)
            messages = trimmed[0] if isinstance(trimmed, tuple) else trimmed
            out = self.llm.invoke(messages)
            return {"messages": [out]}
        
        contexts = _collect_tool_chunks_from_state(state)
        
        history = _format_recent_history(state)
        messages = ANSWER_PROMPT.format_messages(
            question=question,
            contexts=contexts,
            history=history,
        )

        trimmed_result = trim_messages(messages=messages, model=self.model)
        messages = trimmed_result[0] if isinstance(trimmed_result, tuple) else trimmed_result
        out = self.llm.invoke(messages)

        return {"messages": [out]}

    def __route_after_guardrail(self, state: MessagesState) -> str:
        """Routing function: quyết định flow sau Guardrail"""
        route = state.get("route", "needs_info")
        return "generator" if route == "small_talk" else "planner" 

    def __init_Graph(self):
        tools = ToolNode([self._retrieve_tool, self._tavily_tool])
        
        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("guardrail", self.__guardrail)
        graph_builder.add_node("planner", self.__planner)
        graph_builder.add_node("tools", tools)
        graph_builder.add_node("generator", self.__generator)

        graph_builder.add_edge(START, "guardrail")
        graph_builder.add_conditional_edges("guardrail", self.__route_after_guardrail,
            {
                "planner": "planner",
                "generator": "generator",
            },
        )
        graph_builder.add_conditional_edges("planner", tools_condition,
            {
                "tools": "tools",
                END: "generator",
            },
        )
        graph_builder.add_edge("tools", "generator")
        graph_builder.add_edge("generator", END)
        return graph_builder.compile(checkpointer=self.memory)

    def __call__(self, question: str, thread_id: str = "default_session") -> Any:
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke(
            {"messages": [HumanMessage(content=question)]}, config=config # type: ignore
        )
    
    def visualize_graph(self, output_path: str = "graph_diagram.png") -> None:
        try:            
            # Generate graph visualization
            graph_image = self.graph.get_graph().draw_mermaid_png()
            
            # Save to file
            with open(output_path, "wb") as f:
                f.write(graph_image)
        except Exception as e:
            raise RuntimeError(f"Không thể generate graph: {e}")
