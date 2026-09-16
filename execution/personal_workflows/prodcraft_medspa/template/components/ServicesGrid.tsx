import type { Business } from '@/lib/validate';
import { SERVICE_ICONS } from './icons';
import Reveal from './Reveal';

export default function ServicesGrid({ business }: { business: Business }) {
  return (
    <section className="gutter bg-paper py-16 sm:py-24">
      <div className="content-max">
        <Reveal>
          <p className="eyebrow text-ink/60">Services</p>
          <h2 className="font-display mt-3 text-ink" style={{ fontSize: 'clamp(28px, 4vw, 48px)' }}>
            Treatments offered
          </h2>
        </Reveal>

        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {business.services.map((service, i) => {
            const Icon = SERVICE_ICONS[service.icon] ?? SERVICE_ICONS.sparkle;
            return (
              <Reveal key={service.name} className={`delay-${i % 3}`}>
                <div className="flex h-full flex-col gap-4 rounded-2xl border border-black/5 bg-gallery p-6">
                  <div className="text-ink/70">
                    <Icon width={28} height={28} />
                  </div>
                  <div>
                    <h3 className="text-lg font-medium">{service.name}</h3>
                    <p className="mt-1 text-sm text-ink/60">{service.blurb}</p>
                  </div>
                  <a
                    href="#book"
                    className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-ink underline underline-offset-4"
                  >
                    Book a consultation
                    <span aria-hidden="true">&rarr;</span>
                  </a>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
