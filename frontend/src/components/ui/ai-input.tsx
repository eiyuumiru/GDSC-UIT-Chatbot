"use client";

import { CornerRightUp, Mic, Square } from "lucide-react";
import { useState, forwardRef } from "react";

import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/components/hooks/use-auto-resize-textarea";

interface AIInputProps {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  onSubmit?: (value: string) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  className?: string;
  buttonAlignment?: "top" | "bottom";
}

export const AIInput = forwardRef<HTMLDivElement, AIInputProps>(
  function AIInput(
    {
      id = "ai-input",
      placeholder = "Type your message...",
      minHeight = 52,
      maxHeight = 200,
      onSubmit,
      onStop,
      isGenerating = false,
      className,
      buttonAlignment = "bottom",
    },
    ref
  ) {
    const [inputValue, setInputValue] = useState("");

    // 1. Truyền inputValue vào hook để hook tự xử lý
    const { textareaRef } = useAutoResizeTextarea({
      minHeight,
      maxHeight,
      value: inputValue,
    });

    const handleSubmit = () => {
      if (isGenerating) {
        onStop?.();
        return;
      }
      if (!inputValue.trim()) return;
      onSubmit?.(inputValue);
      setInputValue("");
    };

    const buttonPositionClass =
      buttonAlignment === "top" ? "top-4" : "bottom-4";

    return (
      <div ref={ref} className={cn("w-full py-4", className)}>
        <div className="relative max-w-xl w-full mx-auto">
          <Textarea
            id={id}
            placeholder={placeholder}
            className={cn(
              "max-w-xl bg-black/5 dark:bg-white/5 rounded-3xl pl-6 pr-16",
              "placeholder:text-black/50 dark:placeholder:text-white/50",
              "border-none",
              "text-black dark:text-white text-wrap",
              "overflow-y-auto resize-none",
              "focus-visible:ring-0 focus-visible:ring-offset-0 !focus-visible:ring-0 !focus-visible:ring-offset-0 !border-none",
              "transition-[height] duration-100 ease-out",
              "leading-[1.2] py-[16px]",
              "[&::-webkit-resizer]:hidden"
            )}
            style={{
              minHeight: `${minHeight}px`,
              maxHeight: `${maxHeight}px`,
            }}
            rows={1}
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isGenerating) {
                  handleSubmit();
                }
              }
            }}
          />

          {/* Dynamic positioned buttons */}
          <div
            className={cn(
              "absolute rounded-xl bg-black/5 dark:bg-white/5 transition-all duration-200 w-6 h-6 flex items-center justify-center",
              buttonPositionClass,
              inputValue || isGenerating ? "right-11" : "right-3"
            )}
          >
            <Mic className="w-4 h-4 text-black/70 dark:text-white/70" />
          </div>
          <button
            onClick={handleSubmit}
            type="button"
            className={cn(
              "absolute right-3",
              "rounded-xl bg-black/5 dark:bg-white/5 transition-all duration-200 w-6 h-6 flex items-center justify-center",
              buttonPositionClass,
              inputValue || isGenerating
                ? "opacity-100 scale-100"
                : "opacity-0 scale-95 pointer-events-none"
            )}
          >
            {isGenerating ? (
              <Square className="w-2.5 h-2.5 fill-black dark:fill-white animate-pulse" />
            ) : (
              <CornerRightUp className="w-4 h-4 text-black/70 dark:text-white/70" />
            )}
          </button>
        </div>
      </div>
    );
  }
);
