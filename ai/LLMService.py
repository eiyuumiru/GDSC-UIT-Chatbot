from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver

from .RetrieverService.RetrieverService import (
    ContextFormatter,
    RetrieverService,
    make_retrieve_tool,
)

from .SearchAgent import web_search_chunks
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


def _looks_like_uit_info_question(question: str) -> bool:
    q = (question or "").lower().strip()
    if not q:
        return False
    if len(q) < 12:
        return False

    keywords = [
        "uit",
        "uit hcm",
        "uit tp.hcm",
        "đại học công nghệ thông tin",
        "đại học cntt",
        "dh cntt",
        "trường cntt",
        "trường uit",

        # Ngành / khoa / bộ môn
        "khoa học máy tính",
        "khoa hoc may tinh",
        "khoa khmt",
        "khoa khoa học máy tính",
        "kỹ thuật phần mềm",
        "ky thuat phan mem",
        "ktpm",
        "hệ thống thông tin",
        "he thong thong tin",
        "httt",
        "mạng máy tính",
        "mang may tinh",
        "an toàn thông tin",
        "an toan thong tin",
        "khoa học dữ liệu",
        "khoa hoc du lieu",
        "trí tuệ nhân tạo",
        "tri tue nhan tao",
        "ngành",
        "nghanh",
        "chương trình đào tạo",
        "chuong trinh dao tao",
        "chương trình",
        "ctdt",

        # Học phần / môn học / tín chỉ
        "môn học",
        "mon hoc",
        "học phần",
        "hoc phan",
        "tín chỉ",
        "tin chi",
        "số tín chỉ",
        "so tin chi",
        "học lại",
        "hoc lai",
        "học cải thiện",
        "hoc cai thien",
        "học kỳ hè",
        "hoc ky he",

        # Đăng ký học phần / kế hoạch học tập
        "đăng ký học phần",
        "dang ky hoc phan",
        "đăng ký môn",
        "dang ky mon",
        "đăng ký tín chỉ",
        "dang ky tin chi",
        "rút học phần",
        "rut hoc phan",
        "hủy học phần",
        "huy hoc phan",
        "kế hoạch học tập",
        "ke hoach hoc tap",
        "kế hoạch năm học",
        "ke hoach nam hoc",
        "kế hoạch đào tạo",
        "ke hoach dao tao",

        # Học phí / tài chính
        "học phí",
        "hoc phi",
        "miễn giảm học phí",
        "mien giam hoc phi",
        "nộp học phí",
        "nop hoc phi",
        "đóng học phí",
        "dong hoc phi",
        "lịch đóng học phí",
        "lich dong hoc phi",
        "học bổng",
        "hoc bong",
        "miễn giảm",
        "mien giam",

        # Lịch học / lịch thi / lịch nghỉ
        "lịch học",
        "lich hoc",
        "thời khóa biểu",
        "thoi khoa bieu",
        "thời khoá biểu",
        "thoi khoá bieu",
        "lịch thi",
        "lich thi",
        "lịch đăng ký",
        "lich dang ky",
        "lịch khai giảng",
        "lich khai giang",
        "lịch nghỉ",
        "lich nghi",
        "nghỉ tết",
        "nghi tet",
        "tết nguyên đán",
        "tet nguyen dan",
        "tết dương lịch",
        "tet duong lich",
        "nghỉ lễ",
        "nghi le",

        # Tuyển sinh / điểm chuẩn
        "tuyển sinh",
        "tuyen sinh",
        "điểm chuẩn",
        "diem chuan",
        "chỉ tiêu tuyển sinh",
        "chi tieu tuyen sinh",
        "phương thức xét tuyển",
        "phuong thuc xet tuyen",

        # Quy chế / học vụ
        "quy chế",
        "quy che",
        "quy định",
        "quy dinh",
        "quy chế học vụ",
        "quy che hoc vu",
        "quy định học vụ",
        "quy dinh hoc vu",
        "cảnh báo học vụ",
        "canh bao hoc vu",
        "cảnh báo kết quả học tập",
        "canh bao ket qua hoc tap",
        "buộc thôi học",
        "buoc thoi hoc",
        "dừng học vụ",
        "dung hoc vu",
        "đình chỉ học",
        "dinh chi hoc",
        "bảo lưu",
        "bao luu",
        "nghỉ học tạm thời",
        "nghi hoc tam thoi",
        "chuyển ngành",
        "chuyen nganh",
        "xét tốt nghiệp",
        "xet tot nghiep",
        "điều kiện tiên quyết",
        "dieu kien tien quyet",

        # CSVC, thư viện, ký túc xá, dịch vụ
        "cơ sở vật chất",
        "co so vat chat",
        "phòng học",
        "phong hoc",
        "phòng thí nghiệm",
        "phong thi nghiem",
        "thư viện uit",
        "thu vien uit",
        "giờ mở cửa thư viện",
        "gio mo cua thu vien",
        "mượn sách",
        "muon sach",
        "trả sách",
        "tra sach",
        "phòng tự học",
        "phong tu hoc",
        "kí túc xá",
        "ký túc xá",
        "ky tuc xa",

        # Hoạt động sinh viên / đoàn hội
        "câu lạc bộ",
        "cau lac bo",
        "clb",
        "đoàn thanh niên",
        "doan thanh nien",
        "hội sinh viên",
        "hoi sinh vien",

        # Hình thức học
        "học online",
        "hoc online",
        "học trực tuyến",
        "hoc truc tuyen",
    ]
    return any(k in q for k in keywords)


def _needs_source_link(question: str) -> bool:
    q = (question or "").lower()
    if not q:
        return False

    keywords = [
        # Hỏi trực tiếp về nguồn / link / trang web
        "nguồn",
        "nguon",
        "link",
        "liên kết",
        "lien ket",
        "đường link",
        "duong link",
        "đường dẫn",
        "duong dan",
        "trang web",
        "website",
        "web site",
        "url",
        "xem ở đâu",
        "xem o dau",
        "xem tại đâu",
        "xem tai dau",
        "xem ở chỗ nào",
        "xem o cho nao",
        "xem trên web",
        "xem tren web",
        "xem trên website",
        "xem tren website",
        "xem ở đâu trên website",
        "xem o dau tren website",
        "xem ở trang nào",
        "xem o trang nao",
        "xem trên trang nào",
        "xem tren trang nao",
        "trích nguồn",
        "trich nguon",
        "trích link",
        "trich link",
        "trích nguồn web",
        "trich nguon web",
        "trích dẫn web",
        "trich dan web",
        "link chi tiết",
        "link chi tiet",
        "link cụ thể",
        "link cu the",
        "link chính thức",
        "link chinh thuc",
        "website chính thức",
        "website chinh thuc",

        # Hỏi về văn bản / thông báo / công văn / file
        "văn bản",
        "van ban",
        "công văn",
        "cong van",
        "thông báo",
        "thong bao",
        "thông báo số",
        "thong bao so",
        "quyết định số",
        "quyet dinh so",
        "file pdf",
        "pdf",
        "file văn bản",
        "file van ban",
        "văn bản hướng dẫn",
        "van ban huong dan",
        "thông báo hướng dẫn",
        "thong bao huong dan",

        # Các chủ đề nên ưu tiên tìm trên web UIT
        "lịch nghỉ",
        "lich nghi",
        "nghỉ tết",
        "nghi tet",
        "nghỉ hè",
        "nghi he",
        "tết nguyên đán",
        "tet nguyen dan",
        "tết dương lịch",
        "tet duong lich",
        "nghỉ lễ",
        "nghi le",
        "lịch nghỉ tết",
        "lich nghi tet",
        "kế hoạch nghỉ tết",
        "ke hoach nghi tet",

        "học phí",
        "hoc phi",
        "mức thu học phí",
        "muc thu hoc phi",
        "miễn giảm học phí",
        "mien giam hoc phi",
        "nộp học phí",
        "nop hoc phi",
        "đóng học phí",
        "dong hoc phi",
        "phương thức nộp học phí",
        "phuong thuc nop hoc phi",

        "học bổng",
        "hoc bong",
        "học bổng khuyến khích",
        "hoc bong khuyen khich",
        "tiêu chí xét học bổng",
        "tieu chi xet hoc bong",

        "cảnh báo học vụ",
        "canh bao hoc vu",
        "cảnh báo kết quả học tập",
        "canh bao ket qua hoc tap",
        "buộc thôi học",
        "buoc thoi hoc",
        "đình chỉ học",
        "dinh chi hoc",
        "bảo lưu",
        "bao luu",
        "nghỉ học tạm thời",
        "nghi hoc tam thoi",
        "quy chế học vụ",
        "quy che hoc vu",
        "quy định học vụ",
        "quy dinh hoc vu",

        "đăng ký học phần",
        "dang ky hoc phan",
        "hướng dẫn đăng ký học phần",
        "huong dan dang ky hoc phan",
        "đăng ký học hè",
        "dang ky hoc he",
        "kế hoạch học hè",
        "ke hoach hoc he",

        "chương trình đào tạo",
        "chuong trinh dao tao",
        "kế hoạch đào tạo",
        "ke hoach dao tao",
        "ctdt",
    ]
    return any(k in q for k in keywords)


def _fix_links_with_web_results(
    answer: str, domain_to_urls: Dict[str, List[str]]
) -> str:
    """
    Đảm bảo mọi URL trong câu trả lời khớp với deep link mà SearchAgent tìm được
    (nếu cùng domain).
    """
    if not answer or not domain_to_urls:
        return answer

    all_urls: set[str] = set()
    for urls in domain_to_urls.values():
        all_urls.update(urls)

    pattern = re.compile(r"https?://[^\s\)\]]+")

    def _replace(match: re.Match) -> str:
        raw = match.group(0)
        core = raw.rstrip(".,)")
        suffix = raw[len(core) :]

        url = core

        if url in all_urls:
            return url + suffix

        parsed = urlparse(url)
        host = parsed.netloc
        if not host:
            return raw

        candidates = domain_to_urls.get(host)
        if candidates:
            best = candidates[0]
            return best + suffix

        return raw

    return pattern.sub(_replace, answer)


class LLMService(ContextFormatter):
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
        self._retrieve_tool = make_retrieve_tool(self._retriever_service)
        self.graph = self.__init_Graph()

    def __init_Memory(self):
        return MemorySaver()

    def __query_or_response(self, state: MessagesState):
        planner_system = SystemMessage(
            content=(
                "Bạn là chatbot chuyên trả lời về chương trình đào tạo và thông tin học vụ của trường UIT. "
                "Suy luận trong tâm trí (không tiết lộ cho người dùng): "
                "1) Câu hỏi này cần thông tin cụ thể nào? "
                "2) Lịch sử hội thoại đã cung cấp đủ ngữ cảnh chưa? "
                "3) Nếu cần dữ liệu chi tiết từ chương trình đào tạo nội bộ "
                "(ngành, môn học, tín chỉ, điều kiện tiên quyết, lộ trình học, ...), hãy gọi công cụ 'retrieve'. "
                "4) Nếu có thể trả lời từ kiến thức chung hoặc từ lịch sử hội thoại thì không cần gọi công cụ. "
                "Quyết định có gọi công cụ hay không, không giải thích quá trình suy luận."
            )
        )
        llm_with_tools = self.llm.bind_tools([self._retrieve_tool])
        response = llm_with_tools.invoke([planner_system] + state["messages"])
        return {"messages": [response]}

    def __generate_with_context(self, state: MessagesState):
        chunks = _collect_tool_chunks_from_state(state)

        question = _get_last_user_question(state)
        need_source = _needs_source_link(question)
        is_uit_info = _looks_like_uit_info_question(question)

        # Nếu không phải câu UIT, không cần nguồn, không có dữ liệu retriever
        # => giữ nguyên câu trả lời planner (dùng cho chitchat/general).
        if (not chunks) and (not need_source) and (not is_uit_info):
            last_ai = None
            for m in reversed(state["messages"]):
                if m.type == "ai":
                    last_ai = m
                    break
            if last_ai is not None:
                return {"messages": [last_ai]}

        extra_context_text = ""
        web_urls_by_domain: Dict[str, List[str]] = {}

        # Nếu cần nguồn HOẶC (không có chunks nhưng là câu hỏi về UIT)
        # => kích hoạt SearchAgent
        if need_source or ((not chunks) and is_uit_info):
            context_text, web_chunks = web_search_chunks(question)
            if web_chunks:
                chunks = chunks + web_chunks
                for c in web_chunks:
                    url = (
                        (c.get("source") or "")
                        or c.get("metadata", {}).get("source", "")
                    ).strip()
                    if not url:
                        continue
                    parsed = urlparse(url)
                    host = parsed.netloc
                    path = parsed.path or ""
                    if not host:
                        continue
                    if path and path != "/":
                        web_urls_by_domain.setdefault(host, [])
                        if url not in web_urls_by_domain[host]:
                            web_urls_by_domain[host].append(url)

            if context_text and context_text.strip():
                extra_context_text = context_text.strip()

        contexts = self.format_context(chunks)
        if extra_context_text:
            contexts = (
                contexts
                + "\n\n---\n\n"
                + "### Kết quả tìm kiếm từ website UIT (tóm tắt)\n"
                + extra_context_text
            )

        history = _format_recent_history(state)
        messages = ANSWER_PROMPT.format_messages(
            question=question,
            contexts=contexts,
            history=history,
        )
        trimmed_result = trim_messages(messages=messages, model=self.model)
        messages = trimmed_result[0] if isinstance(trimmed_result, tuple) else trimmed_result
        out = self.llm.invoke(messages)

        if web_urls_by_domain:
            fixed = _fix_links_with_web_results(
                str(out.content or ""), web_urls_by_domain
            )
            out.content = fixed

        return {"messages": [out]}

    def __init_Graph(self):
        tools = ToolNode([self._retrieve_tool])
        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("query_or_response", self.__query_or_response)
        graph_builder.add_node("tools", tools)
        graph_builder.add_node("generate_with_context", self.__generate_with_context)

        graph_builder.add_edge(START, "query_or_response")

        # Nếu LLM quyết định gọi tool -> chạy node "tools"
        # Nếu không gọi tool -> chuyển sang generate_with_context
        graph_builder.add_conditional_edges(
            "query_or_response",
            tools_condition,
            {
                "tools": "tools",
                END: "generate_with_context",
            },
        )

        graph_builder.add_edge("tools", "generate_with_context")
        graph_builder.add_edge("generate_with_context", END)

        return graph_builder.compile(checkpointer=self.memory)

    def __call__(self, question: str, thread_id: str = "default_session") -> Any:
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.invoke(
            {"messages": [HumanMessage(content=question)]}, config=config
        )
