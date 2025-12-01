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
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function sendPrompt(
  payload: ChatPayload,
  signal?: AbortSignal
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message: payload.message,
      session_id: payload.sessionId,
      tool_id: payload.toolId ?? null,
      image_base64: payload.imageBase64 ?? null
    }),
    signal
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to send prompt");
  }

  return response.json();
}
