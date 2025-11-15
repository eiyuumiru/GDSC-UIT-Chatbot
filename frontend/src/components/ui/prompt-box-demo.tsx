import * as React from "react";
import { PromptBox } from "@/components/ui/chatgpt-prompt-input";

const makeId = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export function PromptBoxDemo() {
  const [inputKey, setInputKey] = React.useState(() => makeId());

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const message = formData.get("message");
    if (!message && !event.currentTarget.querySelector("img")) {
      return;
    }
    alert("Message Submitted!");
    event.currentTarget.reset();
    setInputKey(makeId());
  };

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background p-4 dark:bg-[#212121]">
      <div className="flex w-full max-w-xl flex-col gap-10">
        <p className="text-center text-3xl text-foreground">How Can I Help You</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <PromptBox key={inputKey} name="message" />
        </form>
      </div>
    </div>
  );
}

