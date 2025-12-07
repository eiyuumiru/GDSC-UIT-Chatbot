import { useRef } from "react";
import 'abortcontroller-polyfill/dist/abortcontroller-polyfill-only';
import {
  AIInput,
  AuroraBackground,
  Conversation,
  ConversationContent,
  ConversationScrollButton,
  ThemeSwitcher,
  ErrorPopup,
} from "@/components/ui";
import { useTheme } from "@/components/providers/theme-provider";
import {
  ASSISTANT_NAME,
  WELCOME_MESSAGE,
  DESCRIPTION,
} from "@/components/constants/text";
import { cn } from "@/lib/utils";
import { useChatSession } from "@/hooks/useChatSession";
import { handleCopyResponse } from "@/lib/chat-utils";
import { ConversationMessage } from "@/components/chat/ConversationMessage";
import { AssistantTypingIndicator } from "@/components/chat/ChatStatus";

export default function App() {
  const { theme, setTheme } = useTheme();
  const abortControllerRef = useRef<AbortController | null>(null);
  const {
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
    handleRestart,
    handleFeedbackToggle,
    handleMessageSubmit,
    handleRetry,
    setError,
  } = useChatSession();

  const handleStop = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  };

  const handleMessageSubmitWithAbort = (message: string) => {
    abortControllerRef.current = new AbortController();
    handleMessageSubmit(message, abortControllerRef.current.signal);
  };

  return (
    <AuroraBackground className="bg-transparent text-foreground items-stretch justify-start">
      <ErrorPopup message={error} onClose={() => setError(null)} />

      {/* Toàn bộ ứng dụng chiếm toàn màn hình */}
      <div className="relative flex flex-col h-dvh w-dvw text-foreground overflow-hidden">
        {!hasUserMessage && (
          <div className="absolute right-4 top-4 z-10">
            <ThemeSwitcher
              value={theme}
              onChange={setTheme}
              className="shadow-sm"
            />
          </div>
        )}

        <main
          className={cn(
            "flex flex-1 justify-center flex-col transition-all duration-500 min-h-0 overflow-hidden", // thêm min-h-0
            hasUserMessage ? "gap-0 pt-8" : "gap-6 pb-20 sm:pb-28 px-4 sm:px-8 lg:px-16"
          )}
        >
          {!hasUserMessage && (
            <div className="flex flex-col items-center gap-4 text-center transition-all duration-500">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                {ASSISTANT_NAME}
              </p>
              <h1 className="text-3xl font-semibold leading-tight sm:text-4xl">
                {WELCOME_MESSAGE}
              </h1>
              <p className="max-w-xl text-sm text-muted-foreground sm:text-base">
                {DESCRIPTION}
              </p>
            </div>
          )}

          {hasUserMessage && (
            <section className="flex flex-col flex-1 w-full min-h-0 space-y-6">
              <header className="flex flex-wrap items-center justify-between gap-4 px-4 sm:px-8 lg:px-16">
                <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Nhật ký hội thoại ·{" "}
                  <span className="text-base font-semibold text-foreground normal-case">
                    Phiên #{sessionId.slice(0, 8)}
                  </span>
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {messages.length} tin nhắn
                  </span>
                  <button
                    type="button"
                    onClick={handleRestart}
                    className="rounded-full bg-foreground/10 px-4 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-foreground/20"
                  >
                    Bắt đầu lại
                  </button>
                  <ThemeSwitcher
                    value={theme}
                    onChange={setTheme}
                    className="shadow-sm"
                  />
                </div>
              </header>

              {/* Vùng có thể cuộn */}
              <Conversation
                key={sessionId}
                className="flex-1 w-full max-w-7xl mx-auto rounded-none border-none bg-transparent overflow-hidden custom-scrollbar"
              >
                <ConversationContent className="flex-col gap-2 pb-40">
                  {messages.map((message) => (
                    <ConversationMessage
                      key={message.id}
                      message={message}
                      assistantControls={
                        message.role === "assistant"
                          ? {
                              onRetry: () => handleRetry(message.id),
                              onCopy: () => handleCopyResponse(message.content),
                              onFeedbackChange: (value) =>
                                handleFeedbackToggle(message.id, value),
                              feedbackValue:
                                messageFeedback[message.id] ?? null,
                              isRegenerating:
                                regeneratingMessageId === message.id,
                              retryDisabled: isSending,
                              copyDisabled:
                                !message.content ||
                                regeneratingMessageId === message.id,
                            }
                          : undefined
                      }
                    />
                  ))}

                  {isSending && !regeneratingMessageId && (
                    <AssistantTypingIndicator />
                  )}
                </ConversationContent>

                {inputHeight > 0 && (
                  <ConversationScrollButton
                    style={{ bottom: `${inputHeight + 48}px` }}
                  />
                )}
              </Conversation>
            </section>
          )}

          {/* Ô nhập cố định */}
          <div
            className={cn(
              "flex flex-col w-full items-center gap-0 pb-2 px-4",
              "transition-all duration-700 ease-in-out",
              hasUserMessage ? "bottom-0 translate-y-0" : "top-1/2"
            )}
          >
            <AIInput
              ref={inputContainerRef}
              key={inputInstanceId}
              placeholder="Nhập câu hỏi của bạn..."
              onSubmit={handleMessageSubmitWithAbort}
              onStop={handleStop}
              isGenerating={isSending}
              buttonAlignment={hasUserMessage ? "bottom" : "top"}
            />
            <p className="text-center text-[11px] pt-2 font-medium text-muted-foreground/60 select-none">
              UIT Hỏi&Đáp có thể mắc lỗi, hãy xác minh các thông tin quan trọng.
            </p>
          </div>
        </main>
      </div>
    </AuroraBackground>
  );
}
