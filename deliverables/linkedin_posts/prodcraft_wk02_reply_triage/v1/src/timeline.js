// ProdCraft weekly notes, wk 02: "32 inboxes, 800 sends. Who replied?"  One timeline for picture, sound and checks.
// Grid: 30 fps, 112.5 BPM, so one beat = 16 frames (0.5333 s), an eighth = 8 frames, a sixteenth = 4 frames:
// every snap, tick and note lands on a whole frame. 52 beats = 13 bars of 4/4 = 832 frames = 27.733 s; the last
// half beat dissolves into frame 0, so the film loops on the bar line.
export const FPS = 30, BPM = 112.5, BEAT = 60 / BPM;           // 0.5333 s
export const b = beats => +(beats * BEAT).toFixed(6);           // beats -> seconds (whole frames by construction)
export const DUR_BEATS = 52;
export const DUR = b(DUR_BEATS);                                // 27.733 s

// ---- beat sheet (beats). Reading-time floor per text: chars / 15 + 1.5 s (readcheck.mjs) ----
export const K = {
  // A. poster: the wk 02 card's headline, header, footer; 32 inbox tiles (F01). Holds 4.5 beats = 2.4 s.
  ribbon: 4.5,          // the 32 tiles snap into a ribbon (1 beat, ripple by distance)
  f05: 4.5,             // gold rule, then the two F05 lines clip in at 4.75 / 5.0 (fully read from 5.5)
  label: 5.0,           // "illustrative replies" (once)
  card0: 5.0,           // 7 reply cards, one per eighth: 5.0 ... 8.0
  headOut: 6.75,        // headline leaves upward (on screen 0 -> 3.6 s; needs 3.5 s)
  reflowUp: 7.25,       // ribbon, label, cards, F05 move up into the headline's space (1 beat)
  lights: 6.5,          // the remaining ribbon tiles light up, one per sixteenth, until 14.5
  // C. rules first
  f05Out: 15.0,         // F05 leaves (on screen 5.5 -> 15.0 beats = 5.07 s; needs 4.77 s)
  knifeRibbon: 15.0,
  rules: 15.5,          // heading "Rules first." (F07)
  reflowC: 15.5,        // ledger re-flows down under the panel
  panel: 15.5,          // code panel slides in from the right, lands on 16.5
  ooo: 17.5,            // OOO rule fires: line 1 lit, the two OOO cards lit
  oooRes: 18.5,         // gold bar moves to the "class" line (as on the card); results stamp in
  oooSort: 19.5,        // OOO rows re-flow to the top
  stop: 20.5, stopSort: 21.5,
  hot: 22.5, hotSort: 23.5,
  rulesOut: 23.5,       // "Rules first." rises out of the heading slot while F15 rises in (one flip)
  f15: 23.5,
  panelOut: 25.5,       // panel leaves (on screen 16.5 -> 25.5 beats = 4.8 s; longest line needs 4.63 s)
  reflowD: 26.0,        // ledger moves up into the panel's space; sorted rows dim
  crm: 26.5,            // "CRM updated" ticks on the three remaining cards: 26.5 / 26.75 / 27.0 (quarter-beat snaps)
  // E. the reframe
  silence: 31.0,        // the score drops to a near-silence for a beat and a half
  knife: 31.5,          // knife cut through the ledger, rows collapse to their midlines
  f15Out: 32.0,
  f19: 32.5,            // three lines clip in 32.5 / 33.0 / 33.5 (fully read from 34.0)
  f18: 34.0,            // "It was" + "30–60" 34.0, then 34.25, 34.5 (fully read from 35.0)
  f18Rule: 35.0,        // a gold rule draws itself under F18, linear, until 46.5
  credits: 41.0,        // two small credit lines clip in 41.0 / 41.5 (fully read from 42.0)
  out: 47.0,            // F19 + F18 leave; end card = header, footer, credits (47.0 -> 52.0 = 2.67 s)
  loop: 51.5,           // half-beat dissolve to frame 0
};

// ---- the replies: invented, generic, ILLUSTRATIVE (FACTS hard rules). Kind -> what the code does with it ----
// Wording uses the reply kinds of F04 and the pattern examples of F11-F13; no names, companies, e-mails or numbers.
export const CARDS = [
  { text: 'Tell me more.', kind: 'rest', tile: 3 },
  { text: 'I’m out of the office until Monday.', kind: 'ooo', tile: 9 },        // F11 "out of office"
  { text: 'Please unsubscribe me.', kind: 'stop', tile: 14 },                    // F12 "unsubscribe"
  { text: 'What does pricing look like?', kind: 'rest', tile: 20 },
  { text: 'Automatic reply: on vacation.', kind: 'ooo', tile: 26 },              // F11 "automatic reply", "on vacation"
  { text: 'Can we jump on a call next week?', kind: 'hot', tile: 6 },            // F13 "can we jump on a call"
  { text: 'Not interested, thanks.', kind: 'rest', tile: 29 },                   // a plain "no" no rule catches
];
// ledger order (top to bottom) after each sort
export const ORDERS = [
  [0, 1, 2, 3, 4, 5, 6],      // as they arrived
  [1, 4, 0, 2, 3, 5, 6],      // after the OOO rule
  [1, 4, 2, 0, 3, 5, 6],      // after the stop rule
  [1, 4, 2, 5, 0, 3, 6],      // after the hot rule: what is left sits at the bottom
];
// result lines (F08 + F14, F09, F10). Nothing is shown for the rest: no model output, name or confidence.
export const RESULT = {
  ooo: 'auto_reply_or_OOO · 0.99 · €0.00 · no model called',
  stop: 'negative · 0.99 · €0.00',
  hot: 'hot · 0.90',
};
export const RULE_TAG = { stop: '_STOP_PATTERNS', hot: '_HOT_PATTERNS' };

// ---- type on screen (FACTS ids) ----
export const TXT = {
  head: ['32 inboxes, 800', 'sends. Who replied?'],                                    // F01 F02 (wk 02 card)
  f05: ['“the bottleneck has simply', 'moved from sending to reading”'],                // F05 (verbatim)
  label: 'illustrative replies',
  rules: 'Rules first.',                                                                // F07
  f15: 'The rest: to the right person, with context.',                                  // F15
  crm: 'CRM updated',                                                                   // F16
  f19: ['The target was never', '800 sends a day', 'for its own sake.'],                // F19 F02
  f18a: 'It was', f18n: '30–60', f18b: 'positive conversations a month,',               // F18
  f18c: 'with booked calls tracked in the CRM.',                                       // F18
  credits: ['Made in code with lemo-opuscar (MIT)', 'music: original, CC0 samples (Versilian Studios)'],
  brand: 'ProdCraft', wk: 'wk 02', foot: 'ProdCraft · weekly notes', page: '02',       // F20
  file: ['self_outbound_system / ', 'reply_classifier.py'], verbatim: 'verbatim',
};
