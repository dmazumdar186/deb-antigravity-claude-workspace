import type { Metadata, Viewport } from 'next';
import { getBusiness } from '@/lib/business';
import { brandCssVars } from '@/lib/color';
import WatermarkBar from '@/components/WatermarkBar';
import MotionController from '@/components/MotionController';
import './globals.css';

export function generateMetadata(): Metadata {
  const business = getBusiness();
  return {
    title: `${business.name} — concept preview`,
    robots: { index: false, follow: false },
  };
}

export function generateViewport(): Viewport {
  const business = getBusiness();
  return {
    themeColor: business.primary_color,
    width: 'device-width',
    initialScale: 1,
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const business = getBusiness();
  const vars = brandCssVars(business.primary_color);

  return (
    <html lang="en">
      {/* Runs before hydration so CSS can key off `html.has-js` to draw the
          scroll-scrubbed sections' resting state correctly; with JS disabled
          this never runs and the `html:not(.has-js)` fallback rules in
          globals.css apply instead (everything stacked, static, visible). */}
      <script
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('has-js');" }}
      />
      <body style={vars as React.CSSProperties}>
        <WatermarkBar business={business} />
        {children}
        <MotionController />
      </body>
    </html>
  );
}
