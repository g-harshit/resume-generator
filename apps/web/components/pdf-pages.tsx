/**
 * The pages of the real PDF, one under another: page 2 starts exactly where the
 * download's does. The server renders them (see `page_images` in the API); the HTML
 * preview can't know where WeasyPrint will break a page.
 */
export function PdfPages({ images, title }: { images: string[]; title: string }) {
  return (
    <div className="flex flex-col gap-3">
      {images.map((src, i) => (
        <figure key={i} className="flex flex-col gap-1">
          <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-sm">
            {/* A data: URL from the API, so next/image's optimiser has nothing to fetch. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={`${title}, page ${i + 1} of ${images.length}`}
              className="block aspect-[210/297] w-full"
            />
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
