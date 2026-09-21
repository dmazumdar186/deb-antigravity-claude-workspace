import type { Business } from '@/lib/validate';

// components/ApproachDrum.tsx
// description: "Your visit" — 4 generic, non-medical-claim steps (Consult,
//   Plan, Treat, Follow up) presented as a sticky numbered "drum" on desktop:
//   MotionController (lib/motion.ts's drumStepState) rotates the steps
//   through a small 3D window as the section scrolls, one step "active"
//   (aria-current="step") at a time. Below 800px, with prefers-reduced-motion,
//   or with JS disabled, it's a plain vertical list — see globals.css.
//   Copy is deliberately generic (no prices, no outcome promises, no
//   before/after language) so it always passes lib/lint.ts unmodified; it is
//   NOT read from business.json, so it never needs linting at build time.
const STEPS = [
  {
    title: 'Consult',
    body: 'Tell us what you want to feel and look like. We talk through options and answer every question.',
  },
  {
    title: 'Plan',
    body: 'We put together a plan built around your goals, your schedule, and what you are comfortable with.',
  },
  {
    title: 'Treat',
    body: 'Your appointment, start to finish, with a licensed provider who explains each step as it happens.',
  },
  {
    title: 'Follow up',
    body: 'We check in after your visit and are here for whatever you need next, from a question to a rebooking.',
  },
];

export default function ApproachDrum({ business }: { business: Business }) {
  return (
    <section className="approach bg-gallery py-16 text-ink sm:py-24" id="approach" data-approach>
      <div className="approach__sticky">
        <div className="approach__heading gutter">
          <p className="eyebrow text-ink/60">How it works</p>
          <h2 className="font-display mt-3 text-ink" style={{ fontSize: 'clamp(34px, 5.5vw, 72px)' }}>
            YOUR VISIT,
            <br />
            START TO FINISH.
          </h2>
          <p className="mt-4 max-w-md text-sm text-ink/70 sm:text-base">
            Four steps, every time you visit {business.name} for a treatment.
          </p>
          <div className="approach__progress" aria-hidden="true">
            <i />
          </div>
        </div>

        <div className="approach__drum">
          <div className="approach__window">
            <ol className="approach__steps">
              {STEPS.map((step, i) => (
                <li key={step.title} data-approach-step aria-current={i === 0 ? 'step' : undefined}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
