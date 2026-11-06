// report.json + report.md: findings grouped per check ID, each with its triage verdict from triage.json.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { RUN, OUT, HERE } from './core.mjs';

export const CHECKS = {
  A1: ['auto', 'E-mail draft: one short https link, 200, no Playground URL'],
  A2: ['auto', 'Boot time shown next to each Option A button; boot screen never blank (hosted boot measured)'],
  A3: ['auto', 'Text blacklist (will appear here, REPLACE, TODO, lorem, undefined, NaN, null, [object Object], {{, %s, XXX) in text and attributes'],
  A4: ['auto', 'Every anchor, src, href, poster, video source answers 200 (or 30x to 200) with the right content type; no mixed content'],
  A5: ['auto', 'Videos: poster, controls, playsinline, preload=metadata, < 25 MB, faststart, decoded frames > 0'],
  A6: ['auto', 'Meaningful <title> and a favicon that answers 200'],
  A7: ['decision', 'Address bar shows « debanjan186 »: operator decision'],
  B1: ['auto', 'No English in French screens (fr-FR and en-GB browsers); hub French only inside « »'],
  B2: ['auto', 'No ISO/US dates; jj/mm/aaaa valid; Paris time; 00:05 Paris clock probe'],
  B3: ['auto', 'Plural agreement after 0, 1, 2 and many'],
  B4: ['auto', 'No mid-word breaks, no line starting with » ; : ! ? or ending with «, no orphan « — exemple » (320/390/768/1280/1440/1920)'],
  B5: ['auto', 'Spell check fr + en (pyspellchecker) with a reasoned allowlist'],
  B6: ['auto', 'Glossary of key labels: same names in the hub and both UIs'],
  B7: ['auto', 'Missing accents / capitals on known words'],
  C1: ['auto', 'No 4xx/5xx, console or page errors in normal use; styled French error pages reached only on purpose'],
  C2: ['auto', 'Every visible non-submit button changes something within 2 s; submit buttons exercised by the journeys'],
  C3: ['auto', 'No empty box: every 0-item list shows a sentence'],
  C4: ['auto', 'CLS ≤ 0.02 per page'],
  C5: ['auto', 'One body family, one display family, one button style family, one accent colour per surface'],
  C6: ['auto', 'No horizontal overflow (six widths); anchors not under the sticky header'],
  C7: ['auto', 'Expired session shows « Session expirée » + login link; purge only idle > 24 h; hub says private + 24 h reset'],
  C8: ['auto', 'No technical residue (errors, stack, JSON braces, wp: markup, hex runs ≥ 16) in visible text'],
  C9: ['auto', 'No test residue in the sample data (fresh browsers)'],
  C10: ['auto', 'Instruction replay: each hub step followed literally by visible labels'],
  D1: ['auto', 'Every « Works in the demo » cell backed by evidence; « Built during the project » not faked by UI'],
  D2: ['auto', 'Fictional people: @example.com, fiction phone ranges, no real congress names'],
  D3: ['auto', 'Every number on the hub is a week, a date, our demo data, or traced to a source line'],
  D4: ['auto', 'No GM&E code in DOM, attributes or inputs outside an approved reveal'],
  E1: ['auto', 'Report names the commit and deployed versions; hub links checked against live versions'],
  E2: ['process', 'Full suites twice green after every change; this gate runs last'],
  E3: ['auto', 'Screenshots taken by this run from fresh contexts on the deployed sites'],
  E4: ['n/a', 'WebKit and Firefox'],
  E5: ['auto', 'Every check at 390 and 1440; B4/C6 at six widths'],
};

const norm = (s) => String(s || '').replace(/\d{2}:\d{2}(:\d{2})?/g, 'HH:MM').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();
export const keyOf = (f) => createHash('sha1').update([f.check, f.option, norm(f.note).replace(/\d+(\.\d+)? ?(s|px|ms)\b/g, 'N'), norm(f.text).slice(0, 120)].join('|')).digest('hex').slice(0, 10);

export function writeReport({ parts, results, hub }) {
  const triage = existsSync(join(HERE, 'triage.json')) ? JSON.parse(readFileSync(join(HERE, 'triage.json'), 'utf8')) : {};
  const groups = new Map();
  for (const f of RUN.findings) {
    const k = keyOf(f);
    if (!groups.has(k)) groups.set(k, { key: k, check: f.check, option: f.option, text: f.text, note: f.note, element: f.element, occurrences: [] });
    const g = groups.get(k);
    if (g.occurrences.length < 40) g.occurrences.push({ page: f.page, role: f.role, width: f.width, locale: f.locale, state: f.state, shot: f.shot, element: f.element });
    g.count = (g.count || 0) + 1;
  }
  // triage: exact key first, then rules (check + regex over text/note/page)
  for (const g of groups.values()) {
    let t = triage.keys && triage.keys[g.key];
    if (!t && triage.rules) for (const r of triage.rules) { if (r.check !== g.check && r.check !== '*') continue; if (r.option && r.option !== g.option) continue; const hay = `${g.text} || ${g.note} || ${g.element} || ${g.occurrences.map((o) => o.page).join(' ')}`; if (new RegExp(r.match, 'i').test(hay)) { t = r; break; } }
    g.status = t ? t.status : 'UNTRIAGED'; g.reason = t ? t.reason : ''; g.ce = t && t.ce ? t.ce : '';
  }
  const list = [...groups.values()].sort((a, b) => (a.check.localeCompare(b.check, 'en', { numeric: true })) || a.option.localeCompare(b.option));
  const per = {};
  for (const id of Object.keys(CHECKS).concat(['GATE'])) per[id] = { REAL: 0, 'FALSE-POSITIVE': 0, UNTRIAGED: 0 };
  // one defect = one CE id: several finding groups (e.g. one per source line) can share a CE id
  const counted = new Set();
  for (const g of list) { const id = `${g.check}|${g.status}|${g.ce || g.key}`; if (counted.has(id)) continue; counted.add(id); per[g.check] = per[g.check] || { REAL: 0, 'FALSE-POSITIVE': 0, UNTRIAGED: 0 }; per[g.check][g.status] = (per[g.check][g.status] || 0) + 1; }
  const perOpt = {}; const seenCe = new Set();
  for (const g of list.filter((x) => x.status === 'REAL')) { const id = g.ce || g.key; if (seenCe.has(id)) continue; seenCe.add(id); perOpt[g.option] = (perOpt[g.option] || 0) + 1; }
  const widths = [...new Set(RUN.coverage.map((c) => c.width))].sort((a, b) => a - b);
  const roles = [...new Set(RUN.coverage.map((c) => `${c.option}:${c.role}`))];
  const meta = { generated: new Date().toISOString(), parts: Object.fromEntries(Object.entries(parts).map(([k, p]) => [k, { at: p.at, findings: p.findings.length, states: p.states.length, logins: p.logins, writing: p.writing, sbx: p.sbx, resets: p.resets, target: p.target }])), states: RUN.states.length, widths, roles, versions: results.versions, checks: RUN.checks };
  const json = { meta, perCheck: per, realPerOption: perOpt, findings: list, replay: { A: (parts.a || {}).replay || [], B: (parts.b || {}).replay || [], Ahosted: (parts.ahosted || {}).replay || [] }, boots: (parts.ahosted || {}).boots || [], claims: results.claims, glossary: results.glossary, styles: results.styles, videos: results.videos, midnight: results.midnight, email: results.email, notes: RUN.notes };
  writeFileSync(join(process.env.CE_OUT ? OUT : HERE, 'report.json'), JSON.stringify(json, null, 1));

  const md = [];
  const esc = (s) => String(s ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');
  md.push('# Client-eye gate report', '', `Generated ${meta.generated}. Commit ${results.versions && results.versions.commit}. Spec: \`28_PreMortem_Client_Eye_Gate.md\`. Machine-readable: \`report.json\`. Triage verdicts: \`triage.json\`. Register: \`../register/CLIENT_EYE.md\`.`, '');
  md.push('## Targets and versions', '');
  const v = results.versions || {};
  md.push(`- Hub: ${hub && hub.tasks ? hub.tasks.length : 0} tasks parsed, group section ${hub && hub.group ? 'present' : 'absent'}; ${Object.entries(v).filter(([k]) => k.startsWith('hub ')).map(([k, x]) => `${k.slice(4)} ${x}`).join(', ')}`);
  md.push(`- Option B Worker: ${typeof v.worker === 'object' ? `${v.worker.id} deployed ${v.worker.created_on}` : v.worker}; custom_demo/src last commit ${v.bSrcLastCommit}`);
  md.push(`- Option A: local Playground ${(parts.a || {}).target || ''} built from the current wp_demo/ (zip ${String(v.zipLocal).slice(0, 12)}); hosted zip ${String(v.zipHosted).slice(0, 12)}`);
  md.push(`- Uncommitted source changes at run time: ${(v.dirty || []).length ? v.dirty.join('; ') : 'none'}`);
  md.push(`- States captured: ${meta.states}; widths ${widths.join(', ')}; roles ${roles.join(', ')}`);
  for (const [k, p] of Object.entries(meta.parts)) md.push(`- Part ${k}: run ${p.at}${p.logins ? `, logins ${p.logins}` : ''}${p.writing && p.writing.length ? `, writing contexts ${p.writing.length}` : ''}${p.sbx ? `, own sandboxes ${p.sbx.length}` : ''}`);
  md.push('', '## Per check', '', '| Check | Type | What | REAL | FALSE-POSITIVE | UNTRIAGED | Status |', '|---|---|---|---|---|---|---|');
  for (const [id, [type, what]] of Object.entries(CHECKS)) {
    const p = per[id] || {};
    const st = RUN.checks[id] ? RUN.checks[id].status : type === 'process' ? 'HUMAN/PROCESS' : (p.REAL || p.UNTRIAGED) ? 'FAIL' : 'PASS';
    md.push(`| ${id} | ${type} | ${esc(what)} | ${p.REAL || 0} | ${p['FALSE-POSITIVE'] || 0} | ${p.UNTRIAGED || 0} | ${st} |`);
  }
  if (per.GATE && (per.GATE.REAL || per.GATE.UNTRIAGED)) md.push('', `Gate errors: ${per.GATE.UNTRIAGED + per.GATE.REAL}`);
  md.push('', '## Check notes', '');
  for (const [id, c] of Object.entries(RUN.checks)) md.push(`- **${id}** ${c.status}: ${c.detail}`);
  md.push('', '## Findings', '');
  for (const id of Object.keys(per)) {
    const fs = list.filter((g) => g.check === id);
    if (!fs.length) continue;
    md.push(`### ${id}`, '', '| CE | Status | Option | Text / element | Note | Where (page · role · width) | Shot | Reason |', '|---|---|---|---|---|---|---|---|');
    for (const g of fs) {
      const o = g.occurrences[0] || {};
      const where = `${esc(o.page)} · ${o.role || ''} · ${[...new Set(g.occurrences.map((x) => x.width))].join('/')}${g.count > 1 ? ` (${g.count}×)` : ''}`;
      md.push(`| ${g.ce || g.key} | ${g.status} | ${g.option} | ${esc(String(g.text).slice(0, 140))}${g.element ? ' · `' + esc(String(g.element).slice(0, 80)) + '`' : ''} | ${esc(g.note).slice(0, 200)} | ${where} | ${o.shot ? o.shot : ''} | ${esc(g.reason)} |`);
    }
    md.push('');
  }
  md.push('## C10 instruction replay', '', '| Option | Task.step | OK | Clicks | Role | Why | Hub text |', '|---|---|---|---|---|---|---|');
  for (const [k, rows] of Object.entries(json.replay)) for (const r of rows) md.push(`| ${k} | ${r.task}.${r.n} | ${r.ok ? 'yes' : 'NO'} | ${r.clicks} | ${r.role} | ${esc(r.why || r.extra)} | ${esc(r.text).slice(0, 140)} |`);
  md.push('', '## D1 claims', '', '| Function | Option | Cell | OK | Evidence |', '|---|---|---|---|---|');
  for (const c of results.claims || []) md.push(`| ${esc(c.fn)} | ${c.option} | ${esc(c.cell).slice(0, 70)} | ${c.ok ? 'yes' : 'NO'} | ${esc(c.evidence)} |`);
  md.push('', '## A2 hosted boots', '');
  for (const b of json.boots) md.push(`- ${b.kind}: first screen after ${b.readySec || 'TIMEOUT'} s; samples ${b.samples.map((s) => `${s.sec}s:${s.visible ? 'content' : 'blank'}`).join(', ')}`);
  md.push('', '## B6 glossary', '', '| Term | A | B | Hub quotes |', '|---|---|---|---|');
  for (const g of results.glossary || []) md.push(`| ${g.term} | ${g.A.join(' / ')} | ${g.B.join(' / ')} | ${g.hub.join(' / ')} |`);
  md.push('', '## Notes', '', ...RUN.notes.map((n) => `- ${esc(n)}`));
  writeFileSync(join(process.env.CE_OUT ? OUT : HERE, 'report.md'), md.join('\n') + '\n');
}
