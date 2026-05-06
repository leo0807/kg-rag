"use client";

/**
 * LatexContent — 将文本中的 $...$ / $$...$$ 渲染为 KaTeX 公式。
 * 无公式时直接返回原字符串，避免不必要的渲染开销。
 */
import "katex/dist/katex.min.css";
import { InlineMath, BlockMath } from "react-katex";

type Segment =
  | { type: "text"; value: string }
  | { type: "inline"; value: string }
  | { type: "block"; value: string };

function parse(text: string): Segment[] {
  const segments: Segment[] = [];
  // 先匹配 $$...$$ 块公式，再匹配 $...$ 行内公式
  // eslint-disable-next-line prefer-regex-literals
  const re = new RegExp("\\$\\$([^$]+?)\\$\\$|\\$([^$\\n]+?)\\$", "g");
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      segments.push({ type: "text", value: text.slice(last, match.index) });
    }
    if (match[1] !== undefined) {
      segments.push({ type: "block", value: match[1] });
    } else if (match[2] !== undefined) {
      segments.push({ type: "inline", value: match[2] });
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    segments.push({ type: "text", value: text.slice(last) });
  }
  return segments;
}

interface Props {
  content: string;
  className?: string;
}

export function LatexContent({ content, className }: Props) {
  if (!content.includes("$")) {
    return <span className={className}>{content}</span>;
  }

  const segments = parse(content);
  return (
    <span className={className}>
      {segments.map((seg, i) => {
        if (seg.type === "text") return <span key={i}>{seg.value}</span>;
        if (seg.type === "block") {
          return (
            <span key={i} className="block my-1">
              <BlockMath math={seg.value} />
            </span>
          );
        }
        return <InlineMath key={i} math={seg.value} />;
      })}
    </span>
  );
}
