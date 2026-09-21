import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { validateBusiness } from './validate';

const EXAMPLE_PATH = path.join(__dirname, '..', 'business.example.json');

describe('validateBusiness', () => {
  it('accepts business.example.json', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    expect(() => validateBusiness(raw)).not.toThrow();
  });

  it('throws listing every missing field', () => {
    expect(() => validateBusiness({})).toThrowError(/schema_version/);
  });

  it('rejects hours arrays that are not exactly 7 entries', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    raw.hours = raw.hours.slice(0, 3);
    expect(() => validateBusiness(raw)).toThrowError(/hours/);
  });

  it('rejects an unknown service icon', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    raw.services[0].icon = 'not-a-real-icon';
    expect(() => validateBusiness(raw)).toThrowError(/icon/);
  });

  it('rejects a non-hex primary_color', () => {
    const raw = JSON.parse(readFileSync(EXAMPLE_PATH, 'utf-8'));
    raw.primary_color = 'blue';
    expect(() => validateBusiness(raw)).toThrowError(/primary_color/);
  });
});
