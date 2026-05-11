"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
  streaming?: boolean;
}

// Ensure a blank line before list blocks so remark-gfm parses them correctly
// when they immediately follow a paragraph (no remark-breaks needed).
function normalizeListSpacing(text: string): string {
  return text.replace(/([^\n])\n([ \t]*[-*+] )/g, "$1\n\n$2");
}

export function AssistantMarkdown({ content, streaming }: Props) {
  return (
    <div className="prose prose-invert prose-sm max-w-none text-sm leading-relaxed text-gray-200 prose-headings:text-gray-100 prose-headings:font-semibold prose-p:text-gray-200 prose-p:leading-relaxed prose-strong:text-gray-100 prose-code:rounded prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:text-xs prose-code:text-indigo-300 prose-pre:rounded-lg prose-pre:border prose-pre:border-gray-700 prose-pre:bg-gray-800 prose-li:text-gray-200 prose-a:no-underline prose-a:text-indigo-400 hover:prose-a:underline prose-blockquote:border-indigo-500 prose-blockquote:text-gray-400 prose-hr:border-gray-700 prose-table:text-gray-200 prose-th:border-gray-700 prose-th:text-gray-100 prose-td:border-gray-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="mb-2 leading-relaxed">{children}</p>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-3 text-base font-semibold text-gray-100">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-2 text-sm font-semibold text-gray-100">
              {children}
            </h3>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-100">{children}</strong>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 list-disc space-y-1 pl-4">{children}</ul>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          code: ({ children }) => (
            <code className="rounded bg-gray-800 px-1 py-0.5 text-xs text-indigo-300">
              {children}
            </code>
          ),
        }}
      >
        {normalizeListSpacing(content)}
      </ReactMarkdown>
      {streaming && (
        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse align-middle bg-indigo-400" />
      )}
    </div>
  );
}
