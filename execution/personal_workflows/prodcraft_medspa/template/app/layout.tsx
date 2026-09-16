import type { Metadata, Viewport } from 'next';
import { getBusiness } from '@/lib/business';
import { brandCssVars } from '@/lib/color';
import WatermarkBar from '@/components/WatermarkBar';
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
      <body style={vars as React.CSSProperties}>
        <WatermarkBar business={business} />
        {children}
      </body>
    </html>
  );
}
