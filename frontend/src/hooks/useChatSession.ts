import { useCallback, useMemo, useState, useRef, useEffect } from "react";
import { sendPrompt } from "@/lib/api";
import type { ChatMessage, AssistantFeedback } from "@/types/chat";
import { createId } from "@/lib/chat-utils";

export const useChatSession = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState(() => createId());
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputInstanceId, setInputInstanceId] = useState(() => createId());
  const [shouldAnimateAnchor, setShouldAnimateAnchor] = useState(false);
  const [messageFeedback, setMessageFeedback] = useState<
    Record<string, AssistantFeedback>
  >({});
  const [regeneratingMessageId, setRegeneratingMessageId] = useState<
    string | null
  >(null);
  const [inputHeight, setInputHeight] = useState(0);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!inputContainerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setInputHeight(entry.contentRect.height);
      }
    });

    observer.observe(inputContainerRef.current);
    return () => observer.disconnect();
  }, []);

  const handleRestart = useCallback(() => {
    setMessages([]);
    setSessionId(createId());
    setInputInstanceId(createId());
    setError(null);
    setShouldAnimateAnchor(false);
    setMessageFeedback({});
    setRegeneratingMessageId(null);
  }, []);

  const hasUserMessage = useMemo(
    () => messages.some((message) => message.role === "user"),
    [messages]
  );

  const handleFeedbackToggle = useCallback(
    (messageId: string, value: AssistantFeedback) => {
      setMessageFeedback((prev) => {
        const current = prev[messageId];
        if (current === value) {
          const next = { ...prev };
          delete next[messageId];
          return next;
        }
        return { ...prev, [messageId]: value };
      });
    },
    []
  );

  const handleMessageSubmit = useCallback(
    async (rawValue: string) => {
      const message = rawValue.trim();
      if (!message || isSending) return;

      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };

      if (!hasUserMessage) {
        setShouldAnimateAnchor(true);
      }

      setMessages((prev) => [...prev, userMessage]);
      setIsSending(true);
      setError(null);

      try {
        const response = await sendPrompt({
          message,
          sessionId,
          toolId: null,
          imageBase64: null,
        });

        setMessages((prev) => [
          ...prev,
          {
            id: createId(),
            role: "assistant",
            content: response.content,
            timestamp: new Date().toISOString(),
          },
        ]);
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.";
        setError(detail);
      } finally {
        setIsSending(false);
      }
    },
    [hasUserMessage, isSending, sessionId]
  );

  const handleRetry = useCallback(
    async (assistantMessageId: string) => {
      if (isSending) return;

      const assistantIndex = messages.findIndex(
        (message) =>
          message.id === assistantMessageId && message.role === "assistant"
      );
      if (assistantIndex === -1) return;

      const previousAssistant = { ...messages[assistantIndex] };
      const userMessage = [...messages]
        .slice(0, assistantIndex)
        .reverse()
        .find((message) => message.role === "user");

      if (!userMessage) return;

      setRegeneratingMessageId(assistantMessageId);
      setIsSending(true);
      setError(null);
      setMessageFeedback((prev) => {
        if (!prev[assistantMessageId]) return prev;
        const next = { ...prev };
        delete next[assistantMessageId];
        return next;
      });
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantMessageId
            ? { ...message, content: "", timestamp: new Date().toISOString() }
            : message
        )
      );

      try {
        const response = await sendPrompt({
          message: userMessage.content,
          sessionId,
          toolId: null,
          imageBase64: null,
        });

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  content: response.content,
                  timestamp: new Date().toISOString(),
                }
              : message
          )
        );
      } catch (err) {
        const detail =
          err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.";
        setError(detail);
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId ? previousAssistant : message
          )
        );
      } finally {
        setIsSending(false);
        setRegeneratingMessageId(null);
      }
    },
    [isSending, messages, sessionId]
  );

  return {
    // State
    messages,
    sessionId,
    isSending,
    error,
    inputInstanceId,
    shouldAnimateAnchor,
    messageFeedback,
    regeneratingMessageId,
    inputHeight,
    hasUserMessage,
    inputContainerRef,

    // Handlers
    handleRestart,
    handleFeedbackToggle,
    handleMessageSubmit,
    handleRetry,
  };
};
