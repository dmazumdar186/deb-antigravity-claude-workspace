import type { Business } from '@/lib/validate';

function formatExpiry(expiresAt: string): string {
  const d = new Date(expiresAt);
  if (Number.isNaN(d.getTime())) return expiresAt;
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}

// Mandatory watermark bar, pinned to the top of every page. `position: sticky`
// (not `fixed`) so its own height reserves real document-flow space — a
// narrow phone wraps the text across 2-3 lines without ever clipping it or
// needing a magic-number spacer to keep it from covering the header.
//
// Deliberately does NOT render `business.preview.watermark` verbatim: that
// field's own copy (e.g. "...Remove: reply 'remove'.") would contradict the
// one opt-out instruction we want on the page. Instead this composes a
// single sentence from `business.name` + `business.preview.expires_at`, with
// the final clause as the `data-remove-link` link (href still
// `business.preview.remove_url`) — exactly one opt-out instruction, never two.
export default function WatermarkBar({ business }: { business: Business }) {
  return (
    <div className="sticky top-0 z-50 bg-ink text-paper" data-watermark>
      <div className="content-max gutter flex flex-col items-center gap-1 py-2 text-center text-[11px] leading-snug sm:flex-row sm:flex-wrap sm:justify-center sm:gap-x-1 sm:gap-y-1">
        <span>
          Concept preview by ProdCraft, not affiliated with or endorsed by {business.name}. Expires{' '}
          {formatExpiry(business.preview.expires_at)}.
        </span>
        <a
          href={business.preview.remove_url}
          data-remove-link
          className="underline underline-offset-2"
        >
          Not for you? Reply &lsquo;no&rsquo; to the email and this preview comes down.
        </a>
      </div>
    </div>
  );
}
