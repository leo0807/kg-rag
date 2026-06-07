"use client";

import Image from "next/image";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
  streaming?: boolean;
}

// [IMG: image_id 说明文字] 解析
const IMG_RE = /\[IMG:\s*(\S+)(?:\s+([^\]]*))?\]/g;

function parseImgTags(text: string): Array<{ type: "text" | "img"; value: string; imageId?: string; caption?: string }> {
  const parts: Array<{ type: "text" | "img"; value: string; imageId?: string; caption?: string }> = [];
  let last = 0;
  let m: RegExpExecArray | null;
  IMG_RE.lastIndex = 0;
  while ((m = IMG_RE.exec(text)) !== null) {
    if (m.index > last) parts.push({ type: "text", value: text.slice(last, m.index) });
    parts.push({ type: "img", value: m[0], imageId: m[1], caption: m[2] || m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
  return parts;
}

function InlineImage({ imageId, caption }: { imageId: string; caption?: string }) {
  const [errored, setErrored] = useState(false);
  const src = `/api/images/${imageId}`;
  if (errored) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-500">
        🖼 {caption || imageId}
      </span>
    );
  }
  return (
    <span className="inline-block my-2 max-w-full">
      <Image
        src={src}
        alt={caption || imageId}
        width={480}
        height={320}
        unoptimized
        className="rounded-lg border border-gray-700 max-w-full"
        onError={() => setErrored(true)}
      />
      {caption && caption !== imageId && (
        <span className="block text-xs text-gray-500 mt-1">{caption}</span>
      )}
    </span>
  );
}

function ContentWithImages({ text }: { text: string }) {
  const parts = parseImgTags(text);
  const hasImgTag = parts.some(p => p.type === "img");
  if (!hasImgTag) return <>{text}</>;
  return (
    <>
      {parts.map((part, i) =>
        part.type === "img" ? (
          <InlineImage key={i} imageId={part.imageId!} caption={part.caption} />
        ) : (
          <span key={i}>{part.value}</span>
        )
      )}
    </>
  );
}

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
            <p className="mb-2 leading-relaxed">
              <ContentWithImages text={typeof children === "string" ? children : ""} />
              {typeof children !== "string" && children}
            </p>
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
