import type { Business } from '@/lib/validate';
import Reveal from './Reveal';

export default function Hero({ business }: { business: Business }) {
  return (
    <section className="gutter bg-paper pb-16 pt-10 sm:pt-16">
      <div className="content-max">
        <Reveal>
          <p className="eyebrow text-ink/60">
            {business.city}, {business.state} &middot; med spa
          </p>
          <h1
            className="font-display mt-4 text-ink"
            style={{ fontSize: 'clamp(40px, 8vw, 104px)' }}
          >
            {business.tagline}
          </h1>
          <p className="mt-6 max-w-xl text-base text-ink/70 sm:text-lg">
            Book any treatment online, any hour, in under a minute.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a href="#book" data-cta="book" className="btn-pill btn-pill-solid">
              Book online
              <span aria-hidden="true">&rarr;</span>
            </a>
            <a href={business.phone_href} className="btn-pill border-ink/25 text-ink">
              Call {business.phone}
            </a>
          </div>
        </Reveal>

        <Reveal className="mt-12">
          <img
            src={`/stock/${business.hero_image}`}
            width={1600}
            height={1000}
            alt={`Abstract editorial artwork evoking ${business.name}'s treatment space`}
            className="w-full rounded-2xl object-cover"
            // Above-the-fold hero image: load eagerly.
            loading="eager"
          />
        </Reveal>
      </div>
    </section>
  );
}
