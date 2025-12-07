import { useState, useEffect } from "react";
import {
  Action,
  Actions,
  Message,
  MessageAvatar,
  MessageContent,
  TextShimmer,
  MarkdownRenderer,
} from "@/components/ui";
import {
  CheckIcon,
  CopyIcon,
  RefreshCcwIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "lucide-react";
import type { ChatMessage, AssistantControls } from "@/types/chat";
import { ASSISTANT_NAME } from "@/components/constants/text";
import humanAvatarSrc from "../../../icons/human.png";
import robotAvatarSrc from "../../../icons/robot.png";

const assistantAvatar = robotAvatarSrc;
const userAvatar = humanAvatarSrc;

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

export function ConversationMessage({
  message,
  assistantControls,
}: {
  message: ChatMessage;
  assistantControls?: AssistantControls;
}) {
  const [isCopied, setIsCopied] = useState(false);
  const isAssistant = message.role === "assistant";
  const avatarSrc = isAssistant ? assistantAvatar : userAvatar;
  const avatarName = isAssistant ? ASSISTANT_NAME : "Bạn";
  const isLiked = assistantControls?.feedbackValue === "like";
  const isDisliked = assistantControls?.feedbackValue === "dislike";
  const shouldShowShimmer = isAssistant && assistantControls?.isRegenerating;

  const handleCopy = () => {
    assistantControls?.onCopy();
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 3000);
  };

  useEffect(() => {
    return () => {
      setIsCopied(false);
    };
  }, [message.id]);

  const renderMessageBody = () => {
    if (!isAssistant) {
      return (
        <MarkdownRenderer
          content={message.content}
          className="break-words text-sm"
          proseClass="prose-invert dark:prose-neutral"
        />
      );
    }

    if (!message.content) {
      return null;
    }

    return (
      <div className="space-y-1.5">
        <MarkdownRenderer
          content={message.content}
          className="break-words text-sm text-left text-foreground"
        />
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
      className={`flex flex-col gap-2 ${
        isAssistant ? "items-start" : "items-end"
      }`}
    >
      <MessageAvatar src={avatarSrc} name={avatarName} />
      <MessageContent>
        {renderMessageBody()}
        <span className="mt-2 block text-[11px] uppercase tracking-wide text-muted-foreground/70">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </MessageContent>
      {isAssistant && assistantControls && (
        <Actions className="mt-1">
          <Action
            label="Thử lại"
            tooltip="Thử lại"
            className="hover:bg-foreground/10"
            onClick={assistantControls.onRetry}
            disabled={assistantControls.retryDisabled}
          >
            <RefreshCcwIcon
              className={`size-4 ${
                assistantControls.isRegenerating
                  ? "animate-spin text-foreground"
                  : ""
              }`}
            />
          </Action>
          <Action
            label="Hữu ích"
            tooltip="Hữu ích"
            className={
              isLiked
                ? "bg-emerald-500/20 text-emerald-600 hover:bg-emerald-500/30 hover:text-emerald-600 dark:bg-emerald-500/25 dark:text-emerald-100 dark:hover:bg-emerald-500/30 dark:hover:text-emerald-100"
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
                ? "bg-red-500/20 text-red-600 hover:bg-red-500/30 hover:text-red-600 dark:bg-red-500/25 dark:text-red-100 dark:hover:bg-red-500/35 dark:hover:text-red-100"
                : ""
            }
            onClick={() => assistantControls.onFeedbackChange("dislike")}
          >
            <ThumbsDownIcon className="size-4" />
          </Action>
          <Action
            label={isCopied ? "Đã sao chép" : "Sao chép"}
            tooltip={isCopied ? "Đã sao chép" : "Sao chép"}
            onClick={handleCopy}
            disabled={assistantControls.copyDisabled}
            className="hover:bg-foreground/10"
          >
            {isCopied ? (
              <CheckIcon className="size-4" />
            ) : (
              <CopyIcon className="size-4" />
            )}
          </Action>
        </Actions>
      )}
    </Message>
  );
}
