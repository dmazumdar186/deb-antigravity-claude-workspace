import type { Business } from '@/lib/validate';

// components/Hero.tsx
// description: Full-viewport, scroll-scrubbed hero (~300vh tall, sticky
//   100vh stage) with 4 numbered copy states driven by business data —
//   "01 / CONSULT" (name + city), "02 / TREAT" (top service), "03 / RECOVER"
//   (second service), "04 / BOOK" (phone CTA) — crossfading between the 4
//   procedural stock stills gen-stock.mjs generates with distinct
//   primary_color-derived palettes (no video, no motion library).
//   MotionController (lib/motion.ts's heroFrame) toggles each state's
//   `is-on` class and fills the step rail's `--fill` custom property as the
//   section scrolls; see globals.css for the crossfade transition and the
//   prefers-reduced-motion / `html:not(.has-js)` fallback that renders every
//   state stacked and fully visible with no transform.
const HERO_IMAGES = ['hero-01.png', 'hero-02.png', 'hero-03.png', 'hero-04.png'];
const HERO_STEPS = ['Consult', 'Treat', 'Recover', 'Book'];

export default function Hero({ business }: { business: Business }) {
  const topService = business.services[0]?.name ?? 'your treatment';
  const secondService = business.services[1]?.name ?? 'your next visit';

  return (
    <section className="hero" id="hero" aria-labelledby="hero-title" data-hero>
      <div className="hero__stage">
        {HERO_IMAGES.map((file, i) => (
          <div className="hero__bg" data-hero-bg={i} key={file}>
            <img
              src={`/stock/${file}`}
              width={1600}
              height={1000}
              alt={`Abstract editorial artwork evoking ${business.name}'s treatment space, mood ${i + 1}`}
              loading={i === 0 ? 'eager' : 'lazy'}
            />
          </div>
        ))}
        <div className="hero__scrim" aria-hidden="true" />

        <div className="hero__copy">
          <div className="hero__state is-on" data-hero-state="0">
            <p className="eyebrow hero__eyebrow">01 / Consult</p>
            <h1 id="hero-title">
              {business.name}
              <br />
              {business.city}, {business.state}
            </h1>
            {/* Deliberately generic, never business-data-driven: keep service
                names out of this first line — they belong in states 02/03. */}
            <p className="hero__lede">Book your next visit online in under a minute.</p>
            <div className="hero__actions">
              <a className="btn-pill btn-pill-solid" href="#book" data-cta="book">
                Book online
                <span aria-hidden="true">&rarr;</span>
              </a>
            </div>
          </div>

          <div className="hero__state" data-hero-state="1">
            <p className="eyebrow hero__eyebrow">02 / Treat</p>
            <h2>
              {topService}
              <br />
              starts here.
            </h2>
            <p className="hero__lede">A consultation, a plan, and a provider who walks you through it.</p>
          </div>

          <div className="hero__state" data-hero-state="2">
            <p className="eyebrow hero__eyebrow">03 / Recover</p>
            <h2>
              Know what
              <br />
              to expect after.
            </h2>
            <p className="hero__lede">
              {secondService} and every treatment here comes with clear aftercare guidance.
            </p>
          </div>

          <div className="hero__state" data-hero-state="3">
            <p className="eyebrow hero__eyebrow">04 / Book</p>
            <h2>
              Your next visit
              <br />
              is one call away.
            </h2>
            <p className="hero__lede">{business.city}, {business.state} &middot; {business.phone}</p>
            <div className="hero__actions hero__actions--final">
              <a className="btn-pill btn-pill-solid" href="#book" data-cta="book">
                Book online
                <span aria-hidden="true">&rarr;</span>
              </a>
              <a className="btn-pill hero__call" href={business.phone_href}>
                Call {business.phone}
              </a>
            </div>
          </div>
        </div>

        <ol className="hero__steps" aria-hidden="true">
          {HERO_STEPS.map((label, i) => (
            <li key={label} data-hero-step={i}>
              {label}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
