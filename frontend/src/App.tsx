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

  return (
    <AuroraBackground className="bg-transparent text-foreground items-stretch justify-start">
      <ErrorPopup message={error} onClose={() => setError(null)} />
      <div className="relative flex min-h-screen w-full flex-col text-foreground">
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
          className={`flex flex-1 flex-col px-4 transition-all duration-500 sm:px-8 lg:px-16 ${
            hasUserMessage ? "gap-10 py-8" : "justify-start gap-6 py-44"
          }`}
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
            <section className="space-y-6">
              <header className="flex flex-wrap items-center justify-between gap-4">
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
              <Conversation className="custom-scrollbar h-[60vh] w-full max-w-2xl mx-auto rounded-none border-none bg-transparent sm:h-[65vh] lg:h-[70vh]">
                <ConversationContent className="flex flex-col gap-2 px-2 sm:px-4 pb-40">
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
                    style={{ bottom: `${inputHeight + 88}px` }}
                  />
                )}
              </Conversation>
            </section>
          )}
        </main>

        <div
          className={cn(
            "fixed left-1/2 -translate-x-1/2 z-50 w-full max-w-2xl px-4",
            "flex flex-col items-center gap-2",
            "transition-all duration-700 ease-in-out",
            hasUserMessage
              ? "bottom-6 translate-y-0" // Trạng thái Chat (Dưới đáy)
              : "bottom-[54vh] translate-y-full" // Trạng thái Ban đầu (Giữa màn hình)
          )}
        >
          <AIInput
            ref={inputContainerRef}
            key={inputInstanceId}
            placeholder="Nhập câu hỏi của bạn..."
            onSubmit={handleMessageSubmit}
            buttonAlignment={hasUserMessage ? "bottom" : "top"}
            className={cn(
              "w-full rounded-3xl px-0",
              "transition-all duration-300 ease-out",
              "bg-background/80 backdrop-blur-md",
              "border border-foreground/10",
              "shadow-none",
              "focus-within:shadow-sm",
              "focus-within:bg-background/95"
            )}
          />
          <p className="text-center text-[11px] font-medium text-muted-foreground/60 select-none">
            UIT Hỏi&Đáp có thể mắc lỗi, hãy xác minh các thông tin quan trọng.
          </p>
        </div>
      </div>
    </AuroraBackground>
  );
}
