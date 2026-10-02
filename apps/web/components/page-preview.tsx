"use client";

import { useEffect, useRef, useState } from "react";

// An A4 page at the 96 dpi browsers lay out at.
const PAGE_W = 794;
const PAGE_H = 1123;

// The API's preview HTML shows the page as a sheet on a grey desk (for a full-size
// view). Shrunk to a card, show just the paper.
const BARE = "<style>html{background:#fff}body{padding:0}.page{box-shadow:none;margin:0}</style>";

/**
 * Rendered resume HTML, scaled to fit its container's width.
 *
 * In a sandboxed iframe with no permissions: the HTML is the same the PDF is made from
 * (so what you see is what you download), it can't run scripts, and its styles can't
 * leak into the app or the app's into it.
 */
export function PagePreview({
  html,
  title,
  bare = false,
  className = "",
}: {
  html: string;
  title: string;
  bare?: boolean;
  className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setScale(entry!.contentRect.width / PAGE_W));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={box}
      className={`relative w-full overflow-hidden bg-surface ${className}`}
      style={{ aspectRatio: `${PAGE_W} / ${PAGE_H}` }}
    >
      {scale > 0 && (
        <iframe
          title={title}
          sandbox=""
          srcDoc={bare ? html.replace("</head>", `${BARE}</head>`) : html}
          tabIndex={-1}
          className="pointer-events-none absolute top-0 left-0 origin-top-left border-0"
          style={{ width: PAGE_W, height: PAGE_H, transform: `scale(${scale})` }}
        />
      )}
    </div>
  );
}
