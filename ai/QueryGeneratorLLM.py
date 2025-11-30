import os
import json
from typing import List

from dotenv import load_dotenv
import litellm  # dùng chung backend Groq qua litellm

# Load biến mt & cấu hình model Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
assert GROQ_API_KEY, "Thiếu GROQ_API_KEY! Vui lòng thêm vào file .env"

# dùng chung Model backend đang dùng cho Chatbot
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")

# Groq API tương thích OpenAI
GROQ_API_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")


SYSTEM_PROMPT = """

Bạn là trợ lý sinh viên của Trường Đại học Công nghệ Thông tin (UIT).
Nhiệm vụ của bạn:

- Nhận một câu hỏi của sinh viên (tiếng Việt hoặc tiếng Anh).
- Sinh ra 1 đến 3 câu truy vấn web thật ngắn gọn, dễ hiểu, 
  phù hợp để tìm kiếm trên các trang web chính thức của UIT 
  (www.uit.edu.vn, oep.uit.edu.vn, daa.uit.edu.vn, ...).
- Chỉ trả về đúng MỘT JSON list các chuỗi query, không thêm giải thích.

Ví dụ output hợp lệ:
["học phí UIT năm 2024", "quy chế học vụ UIT điểm F", "CTĐT ngành KHMT UIT 2023"]

"""

# Hàm core: generate_queries_llm

def generate_queries_llm(question: str, max_queries: int = 3) -> List[str]:
    """
    Dùng LLM (Groq qua litellm) để sinh 1-3 câu truy vấn web từ câu hỏi gốc.

    :param question: Câu hỏi của sinh viên.
    :param max_queries: Số lượng câu query tối đa.
    :return: Danh sách các câu query (list[str]).
    """
    question = (question or "").strip()
    if not question:
        return []

    user_prompt = f"""

Câu hỏi của sinh viên UIT: "{question}"

Hãy sinh ra tối đa {max_queries} câu truy vấn web (search query) ngắn gọn.
Chỉ trả về JSON list các chuỗi, KHÔNG kèm giải thích.
"""

    try:
        response = litellm.completion(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            api_base=GROQ_API_BASE,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=256,
        )

        # litellm trả về format giống OpenAI
        content = response["choices"][0]["message"]["content"].strip()

        # Cố gắng parse JSON trước
        try:
            data = json.loads(content)
            if isinstance(data, list):
                queries = [
                    str(q).strip()
                    for q in data
                    if isinstance(q, (str, int, float)) and str(q).strip()
                ]
                # cắt theo max_queries
                return queries[:max_queries]
        except json.JSONDecodeError:
            pass

        # Fallback: nếu model không trả JSON chuẩn, tách theo dòng/bullet
        lines = [l.strip("-•• ").strip() for l in content.split("\n")]
        queries = [l for l in lines if l]
        return queries[:max_queries]

    except Exception as e:
        # Nếu LLM lỗi, fallback là dùng chính câu hỏi gốc làm 1 query
        print(f"[QueryGeneratorLLM ERROR] {e}")
        return [question]
    
# test nhanh

if __name__ == "__main__":
    print("=== Test generate_queries_llm ===")
    q = input("Nhập câu hỏi của sinh viên UIT: ").strip()
    qs = generate_queries_llm(q, max_queries=3)
    print("\nCác query sinh ra:")
    for i, qq in enumerate(qs, start=1):
        print(f"{i}. {qq}")
