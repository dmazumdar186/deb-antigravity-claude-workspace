import type { Business } from '@/lib/validate';
import { SERVICE_ICONS } from './icons';
import Reveal from './Reveal';

// components/ServicesGrid.tsx
// description: Services as a sticky "folio" stack on desktop — one card per
//   service, pinned in view while the section scrolls, fanning out and
//   receding as MotionController (lib/motion.ts's folioCardState) advances
//   with scroll progress. Below the 800px breakpoint (and with
//   prefers-reduced-motion, and with JS disabled — see globals.css'
//   `html:not(.has-js)` rules) it's a plain stacked reveal grid: no sticky
//   positioning, no transforms, everything simply visible in document flow.
export default function ServicesGrid({ business }: { business: Business }) {
  const count = business.services.length;
  return (
    <section
      className="folio bg-ink py-16 text-paper sm:py-24"
      data-folio
      style={{ '--card-count': count } as React.CSSProperties}
    >
      <div className="gutter content-max">
        <Reveal>
          <p className="eyebrow text-paper/60">Services · 01</p>
          <h2 className="font-display mt-3 text-paper" style={{ fontSize: 'clamp(32px, 5vw, 64px)' }}>
            TREATMENTS
            <br />
            OFFERED.
          </h2>
        </Reveal>
      </div>

      <div className="folio__sticky">
        <div className="folio__stage">
          {business.services.map((service, i) => {
            const Icon = SERVICE_ICONS[service.icon] ?? SERVICE_ICONS.sparkle;
            return (
              <article className="folio-card" data-folio-card key={service.name}>
                <div className="folio-card__inner">
                  <div className="folio-card__icon">
                    <Icon width={32} height={32} />
                  </div>
                  <div className="folio-card__body">
                    <span className="folio-card__index">{String(i + 1).padStart(2, '0')}</span>
                    <h3>{service.name}</h3>
                    <p>{service.blurb}</p>
                  </div>
                  <a href="#book" className="folio-card__cta">
                    <span>Book a consultation</span>
                    <span aria-hidden="true">&rarr;</span>
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
