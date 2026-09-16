import type { Business } from '@/lib/validate';

export default function Footer({ business }: { business: Business }) {
  return (
    <footer className="footer-mobile-safe gutter bg-ink py-12 text-paper/80">
      <div className="content-max flex flex-col gap-4 text-sm">
        <span className="text-base font-medium text-paper">{business.name}</span>
        <a href={business.phone_href} className="w-fit">
          {business.phone}
        </a>
        <span>{business.address}</span>
        <p className="mt-4 max-w-xl text-xs text-paper/50">
          This is a concept preview built by ProdCraft to show what an online-booking-first site
          could look like. It is not affiliated with or endorsed by {business.name}.
        </p>
        <a
          href={business.preview.remove_url}
          data-remove-link
          className="w-fit text-xs text-paper/70 underline underline-offset-2"
        >
          Remove this preview
        </a>
      </div>
    </footer>
  );
}
