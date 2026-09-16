// lib/business.ts
// description: Loads, validates, and content-lints business.json at build
//   time (App Router server components run this during `next build`'s
//   static export — there is no runtime fs access once deployed).
// inputs: business.json at the template root
// outputs: a validated Business object; throws with a clear message on any
//   contract violation or forbidden-term hit, failing the build loudly.

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { validateBusiness, type Business } from './validate';
import { lintStrings } from './lint';

let cached: Business | null = null;

export function getBusiness(): Business {
  if (cached) return cached;

  const filePath = path.join(process.cwd(), 'business.json');
  let raw: string;
  try {
    raw = readFileSync(filePath, 'utf-8');
  } catch (err) {
    throw new Error(
      `Could not read business.json at ${filePath}. Run "npm run build" (it copies ` +
        `business.example.json for you) or write a business.json that matches ` +
        `business.schema.json. Original error: ${(err as Error).message}`
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`business.json is not valid JSON: ${(err as Error).message}`);
  }

  const business = validateBusiness(parsed);

  // Content linter (PROJECT_SPEC.md §7): fail the build if any rendered
  // string contains a forbidden medical-claim term or a "$" price pattern.
  lintStrings([
    { label: 'name', value: business.name },
    { label: 'tagline', value: business.tagline },
    { label: 'address', value: business.address },
    { label: 'preview.watermark', value: business.preview.watermark },
    ...business.services.flatMap((s, i) => [
      { label: `services[${i}].name`, value: s.name },
      { label: `services[${i}].blurb`, value: s.blurb },
    ]),
  ]);

  cached = business;
  return business;
}
