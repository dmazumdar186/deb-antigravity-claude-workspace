import type { Business } from '@/lib/validate';

export default function Header({ business }: { business: Business }) {
  return (
    <header className="gutter border-b border-black/5 bg-paper">
      <div className="content-max flex items-center justify-between py-4">
        <span className="text-base font-medium tracking-tight">{business.name}</span>
        <nav className="flex items-center gap-3">
          <a href={business.phone_href} className="hidden text-sm text-ink/80 sm:inline">
            {business.phone}
          </a>
          <a href="#book" data-cta="book" className="btn-pill btn-pill-solid text-sm">
            Book online
            <span aria-hidden="true">&rarr;</span>
          </a>
        </nav>
      </div>
    </header>
  );
}
