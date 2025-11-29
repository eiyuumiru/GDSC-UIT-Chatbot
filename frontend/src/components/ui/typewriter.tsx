import { useState, useEffect } from "react";

interface TypewriterProps {
  content: string;
  speed?: number;
  className?: string;
  onComplete?: () => void;
}

export function Typewriter({
  content,
  speed = 10,
  className = "",
  onComplete,
}: TypewriterProps) {
  const [displayedContent, setDisplayedContent] = useState("");
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (currentIndex < content.length) {
      const timer = setTimeout(() => {
        setDisplayedContent((prev) => prev + content[currentIndex]);
        setCurrentIndex((prev) => prev + 1);
      }, speed);

      return () => clearTimeout(timer);
    } else if (currentIndex === content.length && onComplete) {
      onComplete();
    }
  }, [currentIndex, content, speed, onComplete]);

  // Reset when content changes
  useEffect(() => {
    setDisplayedContent("");
    setCurrentIndex(0);
  }, [content]);

  return (
    <p className={className}>
      {displayedContent}
      {currentIndex < content.length && (
        <span className="animate-pulse">|</span>
      )}
    </p>
  );
}
