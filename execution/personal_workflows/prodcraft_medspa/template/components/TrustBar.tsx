import type { Business } from '@/lib/validate';
import Reveal from './Reveal';

// components/TrustBar.tsx
// description: The "proof" strip. When the business has real Google reviews
//   (rating + count only — never review text, per CONTRACTS.md) it renders a
//   big editorial stat: rating, stars, review count, linking out to
//   google_maps_url. When there are none (brand-new listing, CSV-imported
//   row), it falls back to a compact hours strip instead of hiding the
//   section entirely — "Please call for current hours." when no hours are
//   set, matching AboutLocation's own fallback copy so the two sections never
//   contradict each other. The map link itself lives on AboutLocation and is
//   untouched here.
function Star({ filled }: { filled: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        d="M12 2.5l2.9 6.1 6.6.7-5 4.5 1.4 6.6L12 17l-5.9 3.4 1.4-6.6-5-4.5 6.6-.7L12 2.5z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function todayHourLabel(business: Business): string {
  const now = new Date();
  // Sun=0..Sat=6 in JS; business.hours is ordered Mon..Sun per business.schema.json/example.
  const order = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const label = order[now.getDay()];
  const today = business.hours.find((h) => h.day.slice(0, 3) === label.slice(0, 3));
  if (!today || !today.open || !today.close) return 'Please call for current hours.';
  return `Open today ${today.open} – ${today.close}`;
}

export default function TrustBar({ business }: { business: Business }) {
  const hasReviews = Boolean(business.review_count && business.review_count >= 1 && business.rating);

  if (hasReviews) {
    const rounded = Math.round(business.rating);
    return (
      <section className="proof gutter bg-ink py-14 text-paper sm:py-20" data-proof="reviews">
        <div className="content-max">
          <Reveal>
            <a href={business.google_maps_url} className="proof__link">
              <p className="eyebrow text-paper/50">Proof</p>
              <div className="proof__stat">
                <span className="proof__rating">{business.rating.toFixed(1)}</span>
                <div className="proof__meta">
                  <span className="proof__stars">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} filled={i < rounded} />
                    ))}
                  </span>
                  <span className="text-sm text-paper/70 sm:text-base">
                    {business.review_count} Google reviews &middot; see them on Google
                  </span>
                </div>
              </div>
            </a>
          </Reveal>
        </div>
      </section>
    );
  }

  const allHoursMissing = business.hours.every((h) => !h.open || !h.close);
  return (
    <section className="proof gutter bg-ink py-14 text-paper sm:py-20" data-proof="hours">
      <div className="content-max">
        <Reveal>
          <p className="eyebrow text-paper/50">Hours</p>
          <p className="mt-3 text-2xl font-medium sm:text-3xl">
            {allHoursMissing ? 'Please call for current hours.' : todayHourLabel(business)}
          </p>
        </Reveal>
      </div>
    </section>
  );
}
