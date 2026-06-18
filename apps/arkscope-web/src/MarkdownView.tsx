// Safe Markdown renderer for AI 研究 answers (gpt-5.5 spec).
//
// - react-markdown + remark-gfm (tables, strikethrough, task lists, autolinks).
// - NO raw HTML: rehype-raw is intentionally NOT used, so any HTML in the answer
//   is shown as escaped TEXT, never injected into the DOM.
// - Links open in a new tab with rel="noopener noreferrer" (don't let an answer
//   navigate/clobber the app).
// - Images are restricted to https:// (block file://, data:, etc.); a blocked
//   image falls back to its alt text.
// Text stays selectable (it's just rendered text). A richer structured/report
// renderer (charts, evidence cards) is a later layer, not this.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function isSafeImageSrc(src: string | undefined): boolean {
  return typeof src === "string" && /^https:\/\//i.test(src.trim());
}

export function MarkdownView({ source }: { source: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ children, href, ...props }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
          img({ src, alt }) {
            // only https images render; anything else (file://, data:, relative)
            // degrades to the alt text so a malicious src is never emitted.
            return isSafeImageSrc(typeof src === "string" ? src : undefined) ? (
              <img src={src as string} alt={alt ?? ""} loading="lazy" />
            ) : (
              <span className="md-img-blocked muted">{alt || "[image]"}</span>
            );
          },
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
