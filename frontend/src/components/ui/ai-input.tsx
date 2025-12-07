"use client";

import { CornerRightUp, Square } from "lucide-react";
import { useState, forwardRef, useEffect } from "react";

import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResizeTextarea } from "@/components/hooks/use-auto-resize-textarea";

export interface AIInputProps {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  onSubmit?: (value: string) => void;
  onStop?: () => void;
  isGenerating?: boolean;
  className?: string;
  buttonAlignment?: "top" | "bottom";
  value?: string;
  onValueChange?: (value: string) => void;
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
      value,
      onValueChange,
    },
    ref
  ) {
    const [inputValue, setInputValue] = useState(value ?? "");
    const isControlled = value !== undefined;
    const currentValue = isControlled ? value : inputValue;

    useEffect(() => {
      if (isControlled) return;
      setInputValue(value ?? "");
    }, [value, isControlled]);

    const { textareaRef } = useAutoResizeTextarea({
      minHeight,
      maxHeight,
      value: currentValue,
    });

    const setValue = (next: string) => {
      if (!isControlled) {
        setInputValue(next);
      }
      onValueChange?.(next);
    };

    const handleSubmit = () => {
      if (isGenerating) {
        onStop?.();
        return;
      }
      if (!currentValue.trim()) return;
      onSubmit?.(currentValue);
      setValue("");
    };

    const buttonPositionClass =
      buttonAlignment === "top" ? "top-3.5" : "bottom-3.5";

    return (
      <div ref={ref} className={cn("w-full", className)}>
        <div className="relative max-w-xl w-full mx-auto">
          <Textarea
            id={id}
            placeholder={placeholder}
            className={cn(
              "max-w-2xl bg-black/5 dark:bg-white/5 rounded-3xl pl-6 pr-16",
              "backdrop-blur-md",
              "placeholder:text-black/50 dark:placeholder:text-white/50",
              "border-none",
              "text-black dark:text-white text-wrap text-base",
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
            value={currentValue}
            onChange={(e) => {
              setValue(e.target.value);
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

          <button
            onClick={handleSubmit}
            type="button"
            className={cn(
              "absolute right-3",
              "rounded-xl bg-black/5 dark:bg-white/5 transition-all duration-200 w-6 h-6 flex items-center justify-center",
              buttonPositionClass,
              currentValue || isGenerating
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
