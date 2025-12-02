import { useCallback, useEffect, useLayoutEffect, useRef } from "react";

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
  value?: string; // <--- Bắt buộc có cái này để theo dõi
}

export function useAutoResizeTextarea({
  minHeight,
  maxHeight,
  value,
}: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto"; // Reset để tính toán lại

    // Tính toán border để đảm bảo chính xác từng pixel
    const computedStyle = window.getComputedStyle(textarea);
    const borderTop = parseFloat(computedStyle.borderTopWidth) || 0;
    const borderBottom = parseFloat(computedStyle.borderBottomWidth) || 0;
    const borderTotal = borderTop + borderBottom;

    const newHeight = Math.max(
      minHeight,
      Math.min(textarea.scrollHeight + borderTotal, maxHeight ?? Number.POSITIVE_INFINITY)
    );

    textarea.style.height = `${newHeight}px`;
  }, [minHeight, maxHeight]);

  // Tự động điều chỉnh khi value thay đổi
  useLayoutEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]); // <--- Dependency quan trọng nhất

  // Resize khi cửa sổ thay đổi
  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}