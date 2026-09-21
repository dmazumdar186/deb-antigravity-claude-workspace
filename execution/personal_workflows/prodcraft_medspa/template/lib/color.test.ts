import { describe, it, expect } from 'vitest';
import { pickInkForBrand, brandCssVars } from './color';

describe('pickInkForBrand', () => {
  it('picks white ink on a dark brand color', () => {
    expect(pickInkForBrand('#0c1120')).toBe('#ffffff');
  });

  it('picks near-black ink on a light brand color', () => {
    expect(pickInkForBrand('#f4f1ea')).toBe('#090a0c');
  });
});

describe('brandCssVars', () => {
  it('returns --brand and --brand-ink', () => {
    const vars = brandCssVars('#7c5cff');
    expect(vars['--brand']).toBe('#7c5cff');
    expect(vars['--brand-ink']).toMatch(/^#/);
  });
});
