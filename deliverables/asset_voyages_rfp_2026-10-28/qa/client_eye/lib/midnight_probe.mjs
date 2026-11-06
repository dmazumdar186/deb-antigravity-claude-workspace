// B2 clock probe: freezes the clock at 00:05 Paris (23:05 UTC the day before) and asks Option B's own date helpers.
// Usage: node midnight_probe.mjs <path to custom_demo/src/lib.js>
const AT = '2026-11-06T23:05:00Z'; // 7 Nov 2026, 00:05 in Paris (UTC+1)
const Real = Date;
const fixed = new Real(AT).getTime();
class FakeDate extends Real {
  constructor(...a) { if (a.length === 0) super(fixed); else super(...a); }
  static now() { return fixed; }
}
globalThis.Date = FakeDate;
const lib = await import((await import('node:url')).pathToFileURL((await import('node:path')).resolve(process.argv[2])).href);
console.log(JSON.stringify({ at: AT, today: lib.today(), parisToday: lib.parisToday(), frDateTime: lib.frDateTime(new FakeDate().toISOString()), frNumDate: lib.frNumDate(lib.parisToday()) }));
