import type { Business } from '@/lib/validate';
import { SERVICE_ICONS } from './icons';
import Reveal from './Reveal';

// components/ServicesGrid.tsx
// description: Services as a sticky "folio" stack on desktop — one card per
//   service, pinned in view while the section scrolls, stacked as upward
//   "tabs" (each back card's index + headline row peeks above the front
//   card) and fanning out as MotionController (lib/motion.ts's folioCardState) advances
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
                  {/* Head row = the "tab" strip that peeks above the card in front
                      on desktop (see globals.css .folio-card__head + lib/motion.ts
                      FOLIO_TAB_Y_PERCENT); index and headline live here so a back
                      card's name is never hidden under the front card. */}
                  <div className="folio-card__head">
                    <span className="folio-card__index">{String(i + 1).padStart(2, '0')}</span>
                    <h3>{service.name}</h3>
                  </div>
                  <div className="folio-card__body">
                    <div className="folio-card__icon">
                      <Icon width={32} height={32} />
                    </div>
                    <p>{service.blurb}</p>
                    <a href="#book" className="folio-card__cta">
                      <span>Book a consultation</span>
                      <span aria-hidden="true">&rarr;</span>
                    </a>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
