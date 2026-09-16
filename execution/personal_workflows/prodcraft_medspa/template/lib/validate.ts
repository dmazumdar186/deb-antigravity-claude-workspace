// lib/validate.ts
// Hand-rolled validator for business.json against business.schema.json's contract.
// Deliberately not a general JSON Schema engine — just enough structural checking
// to give a clear, actionable error message at build time. No ajv dependency.

export interface Hour {
  day: string;
  open: string | null;
  close: string | null;
}

export interface Service {
  name: string;
  blurb: string;
  icon: string;
}

export interface PreviewMeta {
  expires_at: string;
  remove_url: string;
  watermark: string;
}

export interface Business {
  schema_version: string;
  name: string;
  slug: string;
  slug_suffix: string;
  city: string;
  state: string;
  address: string;
  phone: string;
  phone_href: string;
  hours: Hour[];
  services: Service[];
  rating: number;
  review_count: number;
  google_maps_url: string;
  tagline: string;
  primary_color: string;
  accent_color: string;
  hero_image: string;
  preview: PreviewMeta;
  booking_demo: boolean;
}

const ICONS = [
  'syringe',
  'sparkle',
  'laser',
  'droplet',
  'leaf',
  'sun',
  'body',
  'needle',
  'scale',
  'flask',
];

function isNonEmptyString(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0;
}

function isHexColor(v: unknown): v is string {
  return typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
}

/**
 * Validates a parsed JSON value against the business.json contract.
 * Throws an Error listing every missing/invalid field (not just the first) so
 * the build failure is actionable in one pass.
 */
export function validateBusiness(data: unknown): Business {
  const errors: string[] = [];
  const push = (msg: string) => errors.push(msg);

  if (typeof data !== 'object' || data === null) {
    throw new Error('business.json: root value must be an object');
  }
  const b = data as Record<string, unknown>;

  if (!isNonEmptyString(b.schema_version)) push('schema_version: required non-empty string');
  if (!isNonEmptyString(b.name)) push('name: required non-empty string');
  if (!isNonEmptyString(b.slug) || !/^[a-z0-9-]+$/.test(b.slug as string)) {
    push('slug: required, lowercase alnum/hyphen only');
  }
  if (!isNonEmptyString(b.slug_suffix) || !/^[a-z0-9]+$/.test(b.slug_suffix as string)) {
    push('slug_suffix: required, lowercase alnum only');
  }
  if (!isNonEmptyString(b.city)) push('city: required non-empty string');
  if (typeof b.state !== 'string' || b.state.length !== 2) push('state: required 2-letter string');
  if (!isNonEmptyString(b.address)) push('address: required non-empty string');
  if (!isNonEmptyString(b.phone)) push('phone: required non-empty string');
  if (!isNonEmptyString(b.phone_href) || !/^tel:\+?[0-9]+$/.test(b.phone_href as string)) {
    push('phone_href: required, must match tel:+<digits>');
  }

  if (!Array.isArray(b.hours) || b.hours.length !== 7) {
    push('hours: required array of exactly 7 entries');
  } else {
    b.hours.forEach((h, i) => {
      if (typeof h !== 'object' || h === null) {
        push(`hours[${i}]: must be an object`);
        return;
      }
      const hh = h as Record<string, unknown>;
      if (!isNonEmptyString(hh.day)) push(`hours[${i}].day: required non-empty string`);
      if (hh.open !== null && !isNonEmptyString(hh.open)) push(`hours[${i}].open: required string or null`);
      if (hh.close !== null && !isNonEmptyString(hh.close)) push(`hours[${i}].close: required string or null`);
    });
  }

  if (!Array.isArray(b.services) || b.services.length < 3 || b.services.length > 8) {
    push('services: required array of 3-8 entries');
  } else {
    b.services.forEach((s, i) => {
      if (typeof s !== 'object' || s === null) {
        push(`services[${i}]: must be an object`);
        return;
      }
      const ss = s as Record<string, unknown>;
      if (!isNonEmptyString(ss.name)) push(`services[${i}].name: required non-empty string`);
      if (!isNonEmptyString(ss.blurb)) push(`services[${i}].blurb: required non-empty string`);
      if (!isNonEmptyString(ss.icon) || !ICONS.includes(ss.icon as string)) {
        push(`services[${i}].icon: required, one of ${ICONS.join(', ')}`);
      }
    });
  }

  if (typeof b.rating !== 'number' || b.rating < 0 || b.rating > 5) push('rating: required number 0-5');
  if (!Number.isInteger(b.review_count) || (b.review_count as number) < 0) {
    push('review_count: required non-negative integer');
  }
  if (!isNonEmptyString(b.google_maps_url)) push('google_maps_url: required non-empty string');
  if (!isNonEmptyString(b.tagline)) push('tagline: required non-empty string');
  if (!isHexColor(b.primary_color)) push('primary_color: required #rrggbb hex string');
  if (!isHexColor(b.accent_color)) push('accent_color: required #rrggbb hex string');
  if (!isNonEmptyString(b.hero_image)) push('hero_image: required non-empty string');

  if (typeof b.preview !== 'object' || b.preview === null) {
    push('preview: required object');
  } else {
    const p = b.preview as Record<string, unknown>;
    if (!isNonEmptyString(p.expires_at)) push('preview.expires_at: required non-empty string');
    if (!isNonEmptyString(p.remove_url)) push('preview.remove_url: required non-empty string');
    if (!isNonEmptyString(p.watermark)) push('preview.watermark: required non-empty string');
  }

  if (typeof b.booking_demo !== 'boolean') push('booking_demo: required boolean');

  if (errors.length > 0) {
    throw new Error(
      `business.json failed validation (${errors.length} issue${errors.length === 1 ? '' : 's'}):\n` +
        errors.map((e) => `  - ${e}`).join('\n')
    );
  }

  return b as unknown as Business;
}
