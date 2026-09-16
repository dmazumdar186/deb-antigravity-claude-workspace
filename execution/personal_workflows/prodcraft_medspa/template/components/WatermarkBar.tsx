import type { Business } from '@/lib/validate';

function formatExpiry(expiresAt: string): string {
  const d = new Date(expiresAt);
  if (Number.isNaN(d.getTime())) return expiresAt;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}

// Mandatory watermark bar, pinned to the top of every page. `position: sticky`
// (not `fixed`) so its own height reserves real document-flow space — a
// narrow phone wraps the full watermark text across 2-3 lines without ever
// clipping it or needing a magic-number spacer to keep it from covering the
// header. Renders the exact preview.watermark text in full, the expiry date,
// and a "Remove this preview" link (data-remove-link) to preview.remove_url.
export default function WatermarkBar({ business }: { business: Business }) {
  return (
    <div className="sticky top-0 z-50 bg-ink text-paper" data-watermark>
      <div className="content-max gutter flex flex-col items-center gap-1 py-2 text-center text-[11px] leading-snug sm:flex-row sm:flex-wrap sm:justify-center sm:gap-x-2 sm:gap-y-1">
        <span className="break-words">{business.preview.watermark}</span>
        <span className="hidden sm:inline" aria-hidden="true">
          &middot;
        </span>
        <span>This concept expires {formatExpiry(business.preview.expires_at)}</span>
        <span className="hidden sm:inline" aria-hidden="true">
          &middot;
        </span>
        <a
          href={business.preview.remove_url}
          data-remove-link
          className="underline underline-offset-2"
        >
          Remove this preview
        </a>
      </div>
    </div>
  );
}
