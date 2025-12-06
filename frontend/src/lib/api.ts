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

export type ResetResponse = {
  session_id: string;
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

export async function resetSession(
  sessionId: string,
  signal?: AbortSignal
): Promise<ResetResponse> {
  const response = await fetch(`${API_BASE_URL}/chat/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ session_id: sessionId }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to reset session");
  }

  return response.json();
}
