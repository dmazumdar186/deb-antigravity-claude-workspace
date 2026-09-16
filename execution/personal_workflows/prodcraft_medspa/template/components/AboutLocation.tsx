import type { Business } from '@/lib/validate';
import Reveal from './Reveal';

export default function AboutLocation({ business }: { business: Business }) {
  return (
    <section className="gutter bg-paper py-16 sm:py-24">
      <div className="content-max grid grid-cols-1 gap-10 lg:grid-cols-2">
        <Reveal>
          <p className="eyebrow text-ink/60">Location &amp; hours</p>
          <h2 className="font-display mt-3 text-ink" style={{ fontSize: 'clamp(28px, 4vw, 48px)' }}>
            Visit us
          </h2>
          <p className="mt-4 text-sm text-ink/70">{business.address}</p>
          <a
            href={business.google_maps_url}
            className="mt-2 inline-block text-sm font-medium text-ink underline underline-offset-4"
          >
            Get directions
          </a>
        </Reveal>

        <Reveal>
          <table className="hours-table w-full text-sm">
            <tbody>
              {business.hours.map((h) => (
                <tr key={h.day} className="border-b border-black/5">
                  <th scope="row" className="text-left font-medium text-ink/80">
                    {h.day}
                  </th>
                  <td className="text-right text-ink/60">
                    {h.open && h.close ? `${h.open} – ${h.close}` : 'Closed'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
      </div>
    </section>
  );
}
