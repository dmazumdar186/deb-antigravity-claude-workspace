// lib/color.ts
// Turns business.json's primary_color into CSS custom properties, including a
// derived "ink on brand" text color chosen by a real WCAG contrast check
// (falls back between white and near-black, whichever wins by a wider margin).

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  return [r, g, b];
}

// sRGB -> relative luminance, per WCAG 2.x
function relativeLuminance([r, g, b]: [number, number, number]): number {
  const srgb = [r, g, b].map((c) => {
    const cs = c / 255;
    return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}

function contrastRatio(l1: number, l2: number): number {
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Picks the ink color (near-black or white) with the higher WCAG contrast
 * ratio against the given brand hex color.
 */
export function pickInkForBrand(hex: string): string {
  const brandLum = relativeLuminance(hexToRgb(hex));
  const whiteLum = relativeLuminance([255, 255, 255]);
  const blackLum = relativeLuminance([9, 10, 12]); // matches --ink token, #090a0c

  const whiteContrast = contrastRatio(brandLum, whiteLum);
  const blackContrast = contrastRatio(brandLum, blackLum);

  return whiteContrast >= blackContrast ? '#ffffff' : '#090a0c';
}

export function brandCssVars(primaryColor: string): Record<string, string> {
  return {
    '--brand': primaryColor,
    '--brand-ink': pickInkForBrand(primaryColor),
  };
}
