import { MessageAvatar, TextShimmer } from "@/components/ui";
import { ASSISTANT_NAME } from "@/components/constants/text";

import robotAvatarSrc from "../../../icons/robot.png";

const assistantAvatar = robotAvatarSrc;

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

export function AssistantTypingIndicator() {
  return (
    <div className="flex items-center gap-3 py-3 pl-2 text-sm text-muted-foreground">
      <MessageAvatar src={assistantAvatar} name={ASSISTANT_NAME} />
      <AssistantStatusText>Đang chờ phản hồi...</AssistantStatusText>
    </div>
  );
}
