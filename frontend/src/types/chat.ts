export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
};

export type AssistantFeedback = "like" | "dislike";

export type AssistantControls = {
  onRetry: () => void;
  onCopy: () => void;
  onFeedbackChange: (value: AssistantFeedback) => void;
  feedbackValue: AssistantFeedback | null;
  isRegenerating: boolean;
  retryDisabled: boolean;
  copyDisabled: boolean;
};
