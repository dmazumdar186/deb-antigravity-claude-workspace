import type { Business } from '@/lib/validate';

// Sticky bottom bar, mobile only (hidden md+). Must land inside the first
// viewport at 390x844 — it's `fixed`, so it always is.
export default function StickyMobileBar({ business }: { business: Business }) {
  return (
    <div className="gutter fixed inset-x-0 bottom-0 z-40 flex gap-2 border-t border-black/10 bg-paper/95 py-3 backdrop-blur md:hidden">
      <a
        href="#book"
        data-cta="book"
        className="btn-pill btn-pill-solid flex-1 justify-center text-sm"
      >
        Book online
      </a>
      <a
        href={business.phone_href}
        className="btn-pill flex-1 justify-center border-ink/20 text-sm text-ink"
      >
        Call
      </a>
    </div>
  );
}
