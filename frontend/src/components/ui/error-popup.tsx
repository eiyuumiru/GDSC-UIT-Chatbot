import { AlertCircle, X } from "lucide-react";
import { useEffect } from "react";

interface ErrorPopupProps {
  message: string | null;
  onClose: () => void;
}

export function ErrorPopup({ message, onClose }: ErrorPopupProps) {
  useEffect(() => {
    if (!message) return;

    const timer = setTimeout(() => {
      onClose();
    }, 5000);

    return () => clearTimeout(timer);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <div className="fixed top-6 inset-x-0 z-[100] flex justify-center">
      <div className="flex items-center gap-3 px-6 py-3 bg-destructive text-destructive-foreground border border-destructive shadow-lg font-medium text-sm rounded-full backdrop-blur-md animate-in fade-in slide-in-from-top-2">
        <AlertCircle className="size-4 flex-shrink-0" />
        <span className="flex-1">{message}</span>
        <button
          onClick={onClose}
          className="flex-shrink-0 p-1 text-destructive-foreground/80 hover:text-destructive-foreground rounded-full transition-colors"
          aria-label="Close error"
        >
          <X className="size-3" />
        </button>
      </div>
    </div>
  );
}
