import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { lintString, lintStrings } from './lint';
import { validateBusiness } from './validate';

const EXAMPLE_PATH = path.join(__dirname, '..', 'business.example.json');

describe('lintString', () => {
  it('finds no violations in clean copy', () => {
    expect(lintString('Book a consultation for our facial treatments.')).toEqual([]);
  });

  it('flags each forbidden medical-claim term', () => {
    expect(lintString('This treatment is a permanent cure.').length).toBeGreaterThan(0);
    expect(lintString('Guaranteed results every time.').length).toBeGreaterThan(0);
    expect(lintString('FDA approved procedure.').length).toBeGreaterThan(0);
    expect(lintString('Safe for everyone, no side effects.').length).toBeGreaterThan(0);
    expect(lintString('Clinically proven formula.').length).toBeGreaterThan(0);
    expect(lintString('See our before/after gallery.').length).toBeGreaterThan(0);
  });

  it('flags a $ price pattern', () => {
    expect(lintString('Botox starting at $199').length).toBeGreaterThan(0);
  });

  it('is case-insensitive', () => {
    expect(lintString('CLINICALLY PROVEN results').length).toBeGreaterThan(0);
  });
});

describe('lintStrings', () => {
  it('throws a single Error listing every violation', () => {
    expect(() =>
      lintStrings([
        { label: 'a', value: 'cure everything' },
        { label: 'b', value: 'only $50' },
      ])
    ).toThrowError(/2 violations/);
  });

  it('does not throw when all fields are clean', () => {
    expect(() =>
      lintStrings([{ label: 'a', value: 'Book a consultation.' }])
    ).not.toThrow();
  });
});

describe('business.example.json content', () => {
  it('passes validation and the content linter', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    const business = validateBusiness(raw);
    expect(() =>
      lintStrings([
        { label: 'name', value: business.name },
        { label: 'tagline', value: business.tagline },
        { label: 'address', value: business.address },
        { label: 'preview.watermark', value: business.preview.watermark },
        ...business.services.flatMap((s, i) => [
          { label: `services[${i}].name`, value: s.name },
          { label: `services[${i}].blurb`, value: s.blurb },
        ]),
      ])
    ).not.toThrow();
  });

  it('a business.json with a forbidden term fails the linter', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    raw.tagline = 'A guaranteed results permanent cure for aging.';
    const business = validateBusiness(raw);
    expect(() =>
      lintStrings([{ label: 'tagline', value: business.tagline }])
    ).toThrow();
  });
});
