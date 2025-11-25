export type ChatPayload = {
  message: string;
  sessionId: string;
  toolId?: string | null;
  imageBase64?: string | null;
};

export type ChatResponse = {
  session_id: string;
  content: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export async function sendPrompt(payload: ChatPayload): Promise<ChatResponse> {
  // const response = await fetch(`${API_BASE_URL}/chat`, {
  //   method: "POST",
  //   headers: {
  //     "Content-Type": "application/json"
  //   },
  //   body: JSON.stringify({
  //     message: payload.message,
  //     session_id: payload.sessionId,
  //     tool_id: payload.toolId ?? null,
  //     image_base64: payload.imageBase64 ?? null
  //   })
  // });

  // if (!response.ok) {
  //   const detail = await response.text();
  //   throw new Error(detail || "Failed to send prompt");
  // }

  // return response.json();
  throw new Error("Failed to send prompt");

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        session_id: payload.sessionId,
        content: `Đây là phản hồi giả cho tin nhắn: "${payload.message}". Nội dung phản hồi được tạo ra để mô phỏng hành vi của API thực tế. Bạn có thể thay thế nó bằng phản hồi thực tế từ API của bạn. Cảm ơn bạn đã sử dụng dịch vụ của chúng tôi! Chúc bạn một ngày tốt lành! 😊`
      });
    }, 1000);
  });
}

