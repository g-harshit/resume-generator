import type { PageLink } from "@/lib/api";

/**
 * The pages of the real PDF, one under another: page 2 starts exactly where the
 * download's does. The server renders them (see `page_images` in the API); the HTML
 * preview can't know where WeasyPrint will break a page.
 */
export function PdfPages({
  images,
  links = [],
  title,
}: {
  images: string[];
  /** Per page, the PDF's links: made clickable over the image, as in the download. */
  links?: PageLink[][];
  title: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      {images.map((src, i) => (
        <figure key={i} className="flex flex-col gap-1">
          <div className="relative overflow-hidden rounded-lg border border-line bg-surface shadow-sm">
            {/* A data: URL from the API, so next/image's optimiser has nothing to fetch. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={`${title}, page ${i + 1} of ${images.length}`}
              className="block aspect-[210/297] w-full"
            />
            {(links[i] ?? []).map((link, j) => (
              <a
                key={j}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                title={link.url.replace(/^mailto:|^tel:/, "")}
                aria-label={`Open ${link.url.replace(/^mailto:|^tel:/, "")}`}
                className="absolute rounded-sm hover:bg-accent/15 focus-visible:outline-2 focus-visible:outline-accent"
                style={{
                  left: `${link.x * 100}%`,
                  top: `${link.y * 100}%`,
                  width: `${link.w * 100}%`,
                  height: `${link.h * 100}%`,
                }}
              />
            ))}
          </div>
          {images.length > 1 && (
            <figcaption className="text-center text-xs text-muted">
              Page {i + 1} of {images.length}
            </figcaption>
          )}
        </figure>
      ))}
    </div>
  );
}
