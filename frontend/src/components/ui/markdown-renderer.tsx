import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";

interface MarkdownRendererProps {
    content: string;
    className?: string;
    proseClass?: string;
}

export function MarkdownRenderer({ content, className = "", proseClass = "prose-neutral dark:prose-invert" }: MarkdownRendererProps) {
    const processedContent = useMemo(() => {
        return content
            .replace(/\\\[([\s\S]*?)\\\]/g, '$$$$$1$$$$') // Replace \[ ... \] with $$ ... $$
            .replace(/\\\(([\s\S]*?)\\\)/g, '$$$1$$');   // Replace \( ... \) with $ ... $
    }, [content]);

    return (
        <div className={`prose ${proseClass} max-w-none ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeRaw, rehypeKatex]}
                components={{
                    // Customize components if needed
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                            {children}
                        </a>
                    ),
                }}
            >
                {processedContent}
            </ReactMarkdown>
        </div>
    );
}
