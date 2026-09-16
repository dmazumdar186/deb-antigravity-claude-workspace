import { getBusiness } from '@/lib/business';

export default function ExpiredPage() {
  const business = getBusiness();

  return (
    <main className="gutter flex min-h-[60dvh] items-center bg-paper">
      <div className="content-max">
        <p className="eyebrow text-ink/60">Concept preview</p>
        <h1 className="font-display mt-3 text-ink" style={{ fontSize: 'clamp(32px, 6vw, 64px)' }}>
          This preview has expired.
        </h1>
        <p className="mt-4 max-w-lg text-sm text-ink/70 sm:text-base">
          The concept preview for {business.name} is no longer live. Reply to the original email
          to reactivate it, or reach out for a fresh one.
        </p>
        <a
          href={business.preview.remove_url}
          data-remove-link
          className="mt-6 inline-block text-sm font-medium text-ink underline underline-offset-4"
        >
          Remove this preview
        </a>
      </div>
    </main>
  );
}
