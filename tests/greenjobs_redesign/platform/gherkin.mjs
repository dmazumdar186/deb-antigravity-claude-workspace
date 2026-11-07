// A tiny dependency-free Gherkin parser + executor.
// Supports: Feature, Background, Scenario/Example, Scenario Outline/Template + Examples/Scenarios,
// Given/When/Then/And/But/*, tags (ignored), # comments, step data tables (step.table).
// An undefined or ambiguous step FAILS the scenario: there are no silent skips.

const STEP_RE = /^(Given|When|Then|And|But|\*)\s+(.*)$/;

export function parseFeature(text, file = '<memory>') {
  const lines = text.split(/\r?\n/);
  const feature = { file, name: null, background: [], scenarios: [] };
  let section = null; // {kind:'background'|'scenario'|'outline', ...}
  let examples = null;
  const fail = (n, msg) => {
    throw new Error(`${file}:${n + 1}: ${msg}`);
  };
  const closeOutline = () => {
    if (section && section.kind === 'outline') {
      if (!section.examples.length) fail(section.line - 1, `Scenario Outline "${section.name}" has no Examples rows`);
      for (const ex of section.examples) {
        const [head, ...rows] = ex;
        if (!rows.length) fail(section.line - 1, `Examples for "${section.name}" have no data rows`);
        rows.forEach((row, i) => {
          const sub = (s) => s.replace(/<([^<>]+)>/g, (m, k) => (head.includes(k) ? row[head.indexOf(k)] : m));
          feature.scenarios.push({
            name: `${sub(section.name)} [${head.map((h, j) => `${h}=${row[j]}`).join(', ')}]`,
            line: section.line,
            steps: section.steps.map((s) => ({ ...s, text: sub(s.text) })),
            example: i,
          });
        });
      }
    }
  };
  lines.forEach((raw, n) => {
    const line = raw.trim();
    if (!line || line.startsWith('#') || line.startsWith('@')) return;
    let m;
    if ((m = /^Feature:\s*(.*)$/.exec(line))) {
      if (feature.name !== null) fail(n, 'second Feature in one file');
      feature.name = m[1];
      return;
    }
    if (feature.name === null) fail(n, 'content before Feature:');
    if (/^Background:/.test(line)) {
      closeOutline();
      if (feature.scenarios.length) fail(n, 'Background after a Scenario');
      section = { kind: 'background', steps: feature.background };
      return;
    }
    if ((m = /^Scenario (?:Outline|Template):\s*(.*)$/.exec(line))) {
      closeOutline();
      section = { kind: 'outline', name: m[1], line: n + 1, steps: [], examples: [] };
      examples = null;
      return;
    }
    if ((m = /^(?:Scenario|Example):\s*(.*)$/.exec(line))) {
      closeOutline();
      section = { kind: 'scenario', name: m[1], line: n + 1, steps: [] };
      feature.scenarios.push(section);
      examples = null;
      return;
    }
    if (/^(Examples|Scenarios):/.test(line)) {
      if (!section || section.kind !== 'outline') fail(n, 'Examples outside a Scenario Outline');
      examples = [];
      section.examples.push(examples);
      return;
    }
    if (line.startsWith('|')) {
      const cells = line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
      if (examples) {
        examples.push(cells);
        return;
      }
      const last = section?.steps[section.steps.length - 1];
      if (!last) fail(n, 'table without a step');
      (last.table ||= []).push(cells);
      return;
    }
    if ((m = STEP_RE.exec(line))) {
      if (!section) fail(n, 'step outside a Scenario or Background');
      if (examples) fail(n, 'step after Examples');
      section.steps.push({ keyword: m[1], text: m[2], line: n + 1 });
      return;
    }
    if (section === null || (section.steps.length === 0 && !examples)) return; // free-text description
    fail(n, `unparseable line: ${line}`);
  });
  closeOutline();
  if (feature.name === null) throw new Error(`${file}: no Feature`);
  return feature;
}

/** Step registry: keyword-agnostic, regex-matched, like Cucumber. */
export function createRegistry() {
  const defs = [];
  const add = (re, fn) => defs.push({ re: re instanceof RegExp ? new RegExp(`^${re.source}$`, re.flags) : re, fn });
  return {
    defs,
    Given: add,
    When: add,
    Then: add,
    step: add,
    find(text) {
      const hits = defs.map((d) => ({ d, m: d.re.exec(text) })).filter((h) => h.m);
      if (hits.length === 0) throw new Error(`Undefined step: "${text}"`);
      if (hits.length > 1) throw new Error(`Ambiguous step: "${text}" matches ${hits.length} definitions`);
      return hits[0];
    },
  };
}

export async function runScenario(feature, scenario, registry, makeWorld) {
  const world = await makeWorld();
  for (const step of [...feature.background, ...scenario.steps]) {
    try {
      const { d, m } = registry.find(step.text);
      await d.fn.call(world, ...m.slice(1), step.table);
    } catch (e) {
      e.message = `${feature.file}:${step.line} ${step.keyword} ${step.text}\n  ${e.message}`;
      throw e;
    }
  }
  return world;
}
