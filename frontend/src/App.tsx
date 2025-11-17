import { useCallback, useMemo, useState } from "react";
import { sendPrompt } from "@/lib/api";
import {
  AIInput,
  Action,
  AuroraBackground,
  Actions,
  Conversation,
  ConversationContent,
  ConversationScrollButton,
  Message,
  MessageAvatar,
  MessageContent,
  TextEffect,
  TextShimmer,
  ThemeSwitcher
} from "@/components/ui";
import {
  CopyIcon,
  RefreshCcwIcon,
  ThumbsDownIcon,
  ThumbsUpIcon
} from "lucide-react";
import { useTheme } from "@/components/providers/theme-provider";
import humanAvatarSrc from "../icons/human.png";
import robotAvatarSrc from "../icons/robot.png";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
};

type AssistantFeedback = "like" | "dislike";

const createId = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const welcomeMessage = "Xin chào, tôi có thể giúp gì cho bạn?";

const assistantAvatar = robotAvatarSrc;
const userAvatar = humanAvatarSrc;
const assistantName = "UIT HỎI & ĐÁP";

type AssistantControls = {
  onRetry: () => void;
  onCopy: () => void;
  onFeedbackChange: (value: AssistantFeedback) => void;
  feedbackValue: AssistantFeedback | null;
  isRegenerating: boolean;
  retryDisabled: boolean;
  copyDisabled: boolean;
};

function ConversationMessage({
  message,
  assistantControls
}: {
  message: ChatMessage;
  assistantControls?: AssistantControls;
}) {
  const isAssistant = message.role === "assistant";
  const avatarSrc = isAssistant ? assistantAvatar : userAvatar;
  const avatarName = isAssistant ? assistantName : "Bạn";
  const isLiked = assistantControls?.feedbackValue === "like";
  const isDisliked = assistantControls?.feedbackValue === "dislike";
  const shouldShowShimmer = isAssistant && assistantControls?.isRegenerating;
  const renderMessageBody = () => {
    if (!isAssistant) {
      return <p className="whitespace-pre-line text-sm leading-relaxed">{message.content}</p>;
    }

    if (!message.content) {
      return null;
    }

    const responseLines = message.content.split(/\r?\n/);

    return (
      <div className="space-y-1.5">
        {responseLines.map((line, idx) =>
          line.trim().length ? (
            <TextEffect
              key={`${message.id}-line-${idx}`}
              per="char"
              preset="fade"
              as="p"
              className="font-medium text-left text-foreground text-sm leading-relaxed tracking-normal"
            >
              {line}
            </TextEffect>
          ) : (
            <span key={`${message.id}-gap-${idx}`} className="block h-2" aria-hidden="true" />
          )
        )}
      </div>
    );
  };

  if (shouldShowShimmer) {
    return (
      <div className="flex items-center gap-3 py-3 pl-2 text-sm text-muted-foreground">
        <MessageAvatar src={avatarSrc} name={avatarName} />
        <AssistantStatusText>Đang chờ phản hồi...</AssistantStatusText>
      </div>
    );
  }

  return (
    <Message
      from={isAssistant ? "assistant" : "user"}
      className={`flex flex-col gap-2 ${isAssistant ? "items-start" : "items-end"}`}
    >
      <MessageAvatar src={avatarSrc} name={avatarName} />
      <MessageContent>
        {renderMessageBody()}
        <span className="mt-2 block text-[11px] uppercase tracking-wide text-muted-foreground/70">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </MessageContent>
      {isAssistant && assistantControls && (
        <Actions className="mt-1">
          <Action
            label="Thử lại"
            tooltip="Thử lại"
            onClick={assistantControls.onRetry}
            disabled={assistantControls.retryDisabled}
          >
            <RefreshCcwIcon
              className={`size-4 ${assistantControls.isRegenerating ? "animate-spin text-foreground" : ""}`}
            />
          </Action>
          <Action
            label="Hữu ích"
            tooltip="Hữu ích"
            className={
              isLiked
                ? "bg-emerald-500/20 text-emerald-600 hover:bg-emerald-500/30 dark:bg-emerald-500/25 dark:text-emerald-100 dark:hover:bg-emerald-500/30"
                : ""
            }
            onClick={() => assistantControls.onFeedbackChange("like")}
          >
            <ThumbsUpIcon className="size-4" />
          </Action>
          <Action
            label="Chưa ổn"
            tooltip="Chưa ổn"
            className={
              isDisliked
                ? "bg-red-500/20 text-red-600 hover:bg-red-500/30 dark:bg-red-500/25 dark:text-red-100 dark:hover:bg-red-500/35"
                : ""
            }
            onClick={() => assistantControls.onFeedbackChange("dislike")}
          >
            <ThumbsDownIcon className="size-4" />
          </Action>
          <Action
            label="Sao chép"
            tooltip="Sao chép"
            onClick={assistantControls.onCopy}
            disabled={assistantControls.copyDisabled}
          >
            <CopyIcon className="size-4" />
          </Action>
        </Actions>
      )}
    </Message>
  );
}

function AssistantStatusText({ children }: { children: string }) {
  return (
    <TextShimmer
      className="text-sm font-semibold uppercase tracking-wide"
      duration={1}
    >
      {children}
    </TextShimmer>
  );
}

function AssistantTypingIndicator() {
  return (
    <div className="flex items-center gap-3 py-3 pl-2 text-sm text-muted-foreground">
      <MessageAvatar src={assistantAvatar} name={assistantName} />
      <AssistantStatusText>Đang chờ phản hồi...</AssistantStatusText>
    </div>
  );
}

export default function App() {
  const { theme, setTheme } = useTheme();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState(() => createId());
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputInstanceId, setInputInstanceId] = useState(() => createId());
  const [shouldAnimateAnchor, setShouldAnimateAnchor] = useState(false);
  const [messageFeedback, setMessageFeedback] = useState<Record<string, AssistantFeedback>>({});
  const [regeneratingMessageId, setRegeneratingMessageId] = useState<string | null>(null);

  const handleReset = () => {
    setMessages([]);
    setSessionId(createId());
    setInputInstanceId(createId());
    setError(null);
    setShouldAnimateAnchor(false);
    setMessageFeedback({});
    setRegeneratingMessageId(null);
  };

  const hasUserMessage = useMemo(
    () => messages.some((message) => message.role === "user"),
    [messages]
  );

  const handleFeedbackToggle = useCallback((messageId: string, value: AssistantFeedback) => {
    setMessageFeedback((prev) => {
      const current = prev[messageId];
      if (current === value) {
        const next = { ...prev };
        delete next[messageId];
        return next;
      }
      return { ...prev, [messageId]: value };
    });
  }, []);

  const handleCopyResponse = useCallback((content: string) => {
    if (!content) return;

    const fallbackCopy = () => {
      if (typeof document === "undefined") return;
      const textarea = document.createElement("textarea");
      textarea.value = content;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(textarea);
      }
    };

    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(content).catch(fallbackCopy);
    } else {
      fallbackCopy();
    }
  }, []);

  const handleMessageSubmit = useCallback(
    async (rawValue: string) => {
      const message = rawValue.trim();
      if (!message || isSending) return;

      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: message,
        timestamp: new Date().toISOString()
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
          imageBase64: null
        });

        setMessages((prev) => [
          ...prev,
          {
            id: createId(),
            role: "assistant",
            content: response.content,
            timestamp: new Date().toISOString()
          }
        ]);
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.";
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
        (message) => message.id === assistantMessageId && message.role === "assistant"
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
          imageBase64: null
        });

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  content: response.content,
                  timestamp: new Date().toISOString()
                }
              : message
          )
        );
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định.";
        setError(detail);
        setMessages((prev) =>
          prev.map((message) => (message.id === assistantMessageId ? previousAssistant : message))
        );
      } finally {
        setIsSending(false);
        setRegeneratingMessageId(null);
      }
    },
    [isSending, messages, sessionId]
  );

  return (
    <AuroraBackground className="bg-transparent text-foreground items-stretch justify-start">
      <div className="relative flex min-h-screen w-full flex-col text-foreground">
        {!hasUserMessage && (
          <div className="absolute right-4 top-4 z-10">
            <ThemeSwitcher value={theme} onChange={setTheme} className="shadow-sm" />
          </div>
        )}
        <main
          className={`flex flex-1 flex-col px-4 transition-all duration-500 sm:px-8 lg:px-16 ${
            hasUserMessage ? "gap-10 py-8" : "justify-center gap-6 py-6"
          }`}
        >
        {!hasUserMessage && (
          <div className="flex flex-col items-center gap-4 text-center transition-all duration-500">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              {assistantName}
            </p>
            <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">{welcomeMessage}</h1>
            <p className="max-w-xl text-sm text-muted-foreground sm:text-base">
              Đặt câu hỏi về chương trình đào tạo, môn học, tín chỉ hay học phần tự chọn của trường UIT.
              Tôi sẽ cố gắng phản hồi chính xác và ngắn gọn nhất.
            </p>
          </div>
        )}

        {hasUserMessage && (
          <section className="space-y-6">
            <header className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Nhật ký hội thoại ·{" "}
                <span className="text-base font-semibold text-foreground normal-case">
                  Phiên #{sessionId.slice(0, 8)}
                </span>
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-muted-foreground">{messages.length} tin nhắn</span>
                <button
                  type="button"
                  onClick={handleReset}
                  className="rounded-full bg-foreground/10 px-4 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-foreground/20"
                >
                  Bắt đầu lại
                </button>
                <ThemeSwitcher value={theme} onChange={setTheme} className="shadow-sm" />
              </div>
            </header>
            <Conversation className="custom-scrollbar h-[60vh] w-full rounded-none border-none bg-transparent sm:h-[65vh] lg:h-[70vh]">
              <ConversationContent className="flex flex-col gap-2 px-2 sm:px-4">
                {messages.map((message) => (
                  <ConversationMessage
                    key={message.id}
                    message={message}
                    assistantControls={
                      message.role === "assistant"
                        ? {
                            onRetry: () => handleRetry(message.id),
                            onCopy: () => handleCopyResponse(message.content),
                            onFeedbackChange: (value) => handleFeedbackToggle(message.id, value),
                            feedbackValue: messageFeedback[message.id] ?? null,
                            isRegenerating: regeneratingMessageId === message.id,
                            retryDisabled: isSending,
                            copyDisabled: !message.content || regeneratingMessageId === message.id
                          }
                        : undefined
                    }
                  />
                ))}
                {isSending && !regeneratingMessageId && <AssistantTypingIndicator />}
              </ConversationContent>
              <ConversationScrollButton />
            </Conversation>
          </section>
        )}

        <section
          className={`w-full space-y-3 transition-all duration-500 ${
            hasUserMessage ? "mt-auto" : "mx-auto max-w-2xl"
          } ${shouldAnimateAnchor ? "animate-slide-down-chat" : ""}`}
        >
          <AIInput
            key={inputInstanceId}
            placeholder="Nhập câu hỏi của bạn..."
            onSubmit={handleMessageSubmit}
            className={`w-full transition-all duration-500 ${
              hasUserMessage ? "" : "max-w-2xl animate-fade-scale"
            }`}
          />
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
        </section>
      </main>
      </div>
    </AuroraBackground>
  );
}

