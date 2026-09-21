'use client';

// components/BookingWidget.tsx
// The #book demo booking widget: a month calendar, time slots, a service
// select, and a disabled "Confirm" state that reveals a plain-language demo
// disclaimer. Entirely client-side — no form submission, no network call, no
// PII fields (no name/email/phone inputs) anywhere in this component.

import { useMemo, useState } from 'react';
import type { Business } from '@/lib/validate';

const TIME_SLOTS = ['9:00 AM', '10:30 AM', '12:00 PM', '1:30 PM', '3:00 PM', '4:30 PM'];

function buildMonthGrid(year: number, month: number): (number | null)[] {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  return cells;
}

export default function BookingWidget({ business }: { business: Business }) {
  const today = useMemo(() => new Date(), []);
  const [selectedDay, setSelectedDay] = useState<number | null>(today.getDate());
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [selectedService, setSelectedService] = useState<string>(business.services[0]?.name ?? '');
  const [showDemoNote, setShowDemoNote] = useState(false);

  const year = today.getFullYear();
  const month = today.getMonth();
  const monthLabel = today.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  const cells = useMemo(() => buildMonthGrid(year, month), [year, month]);

  return (
    <section id="book" className="gutter scroll-mt-24 bg-gallery py-16 sm:py-24">
      <div className="content-max">
        <p className="eyebrow text-ink/60">Book online</p>
        <h2 className="font-display mt-3 text-ink" style={{ fontSize: 'clamp(28px, 4vw, 48px)' }}>
          See it in action
        </h2>
        <p className="mt-3 max-w-xl text-sm text-ink/60">
          This is a working demo of the booking flow &mdash; pick a date, a time, and a service.
        </p>

        <div className="mt-10 grid grid-cols-1 gap-6 rounded-2xl border border-black/5 bg-paper p-6 sm:p-8 lg:grid-cols-2">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{monthLabel}</span>
            </div>
            <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs text-ink/50">
              {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
                <div key={`${d}-${i}`}>{d}</div>
              ))}
            </div>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {cells.map((day, i) => (
                <button
                  key={i}
                  type="button"
                  disabled={day === null}
                  onClick={() => {
                    setSelectedDay(day);
                    setShowDemoNote(false);
                  }}
                  className={`aspect-square rounded-lg text-sm transition ${
                    day === null
                      ? 'cursor-default'
                      : day === selectedDay
                        ? 'bg-[var(--brand)] text-[var(--brand-ink)]'
                        : 'hover:bg-black/5'
                  }`}
                >
                  {day ?? ''}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-6">
            <div>
              <label htmlFor="service-select" className="text-sm font-medium">
                Service
              </label>
              <select
                id="service-select"
                value={selectedService}
                onChange={(e) => {
                  setSelectedService(e.target.value);
                  setShowDemoNote(false);
                }}
                className="mt-2 w-full rounded-lg border border-black/10 bg-paper px-3 py-2 text-sm"
              >
                {business.services.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <span className="text-sm font-medium">Time</span>
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                {TIME_SLOTS.map((slot) => (
                  <button
                    key={slot}
                    type="button"
                    onClick={() => {
                      setSelectedSlot(slot);
                      setShowDemoNote(false);
                    }}
                    className={`rounded-lg border px-3 py-2 text-sm transition ${
                      slot === selectedSlot
                        ? 'border-[var(--brand)] bg-[var(--brand)] text-[var(--brand-ink)]'
                        : 'border-black/10 hover:border-black/30'
                    }`}
                  >
                    {slot}
                  </button>
                ))}
              </div>
            </div>

            {/*
              "Confirm" never actually submits anything — it is a demo state,
              not a real booking action. It stays clickable (a truly `disabled`
              button would swallow the click) but its only effect is to reveal
              the disclaimer below; nothing is sent anywhere.
            */}
            <button
              type="button"
              aria-disabled="true"
              onClick={() => setShowDemoNote(true)}
              className="btn-pill btn-pill-solid mt-2 justify-center opacity-60"
            >
              Confirm
            </button>

            {showDemoNote && (
              <p className="text-sm text-ink/70" role="status">
                Demo only. Nothing is sent. Your real booking system plugs in here.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
