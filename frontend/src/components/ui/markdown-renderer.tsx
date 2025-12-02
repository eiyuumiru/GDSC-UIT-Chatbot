import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
    content: string;
    className?: string;
    proseClass?: string;
}

export function MarkdownRenderer({ content, className = "", proseClass = "prose-neutral dark:prose-invert" }: MarkdownRendererProps) {
    return (
        <div className={`prose ${proseClass} max-w-none ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
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
                {content}
            </ReactMarkdown>
        </div>
    );
}
