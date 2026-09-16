import type { Business } from '@/lib/validate';
import Reveal from './Reveal';

function Star({ filled }: { filled: boolean }) {
  return (
    <svg
      width="16"
      height="16"
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

export default function TrustBar({ business }: { business: Business }) {
  const rounded = Math.round(business.rating);
  return (
    <section className="gutter border-y border-black/5 bg-gallery py-6">
      <div className="content-max">
        <Reveal>
          <a
            href={business.google_maps_url}
            className="flex flex-wrap items-center gap-3 text-sm text-ink/80 hover:text-ink"
          >
            <span className="flex text-amber-500">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star key={i} filled={i < rounded} />
              ))}
            </span>
            <span>
              {business.rating.toFixed(1)} &middot; {business.review_count} Google reviews
            </span>
          </a>
        </Reveal>
      </div>
    </section>
  );
}
