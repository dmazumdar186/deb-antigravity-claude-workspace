// BDD runner: parses build/features/*.feature and executes every scenario against the Worker's
// fetch with offline fakes. Undefined/ambiguous steps fail the run; an empty feature dir fails too.
//   node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs'

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createRegistry, parseFeature, runScenario } from './gherkin.mjs';
import { registerSteps } from './bdd_steps.mjs';
import { FEATURES_DIR } from './helpers.mjs';

const registry = createRegistry();
registerSteps(registry);

const REQUIRED = ['applications_inbox.feature', 'boards_current_jobs.feature', 'posting_console.feature'];
const files = readdirSync(FEATURES_DIR).filter((f) => f.endsWith('.feature')).sort();

test('all three floor-scope feature files are present', () => {
  for (const f of REQUIRED) assert.ok(files.includes(f), `missing ${f}`);
});

const features = files.map((f) => parseFeature(readFileSync(join(FEATURES_DIR, f), 'utf8'), f));

test('every step in every feature has exactly one definition (no silent skips)', () => {
  const problems = [];
  for (const feat of features) {
    for (const sc of [{ steps: feat.background }, ...feat.scenarios]) {
      for (const s of sc.steps) {
        try {
          registry.find(s.text);
        } catch (e) {
          problems.push(`${feat.file}:${s.line} ${e.message}`);
        }
      }
    }
  }
  assert.deepEqual(problems, []);
});

for (const feat of features) {
  describe(`Feature: ${feat.name}`, () => {
    assert.ok(feat.scenarios.length > 0, `${feat.file} has no scenarios`);
    for (const sc of feat.scenarios) {
      test(`Scenario: ${sc.name}`, async () => {
        await runScenario(feat, sc, registry, async () => ({}));
      });
    }
  });
}

// ---------- the runner itself ----------

describe('gherkin runner self-test', () => {
  const sample = `
@tag
Feature: Sample
  free description line
  Background:
    Given a counter at 1
  Scenario Outline: add <n>
    When I add <n>
    Then the counter is <total>
    Examples:
      | n | total |
      | 2 | 3     |
      | 5 | 6     |
  Scenario: plain
    * I add 1
    But the counter is 2
`;
  const reg = () => {
    const r = createRegistry();
    r.Given(/a counter at (\d+)/, function (n) {
      this.c = Number(n);
    });
    r.When(/I add (\d+)/, function (n) {
      this.c += Number(n);
    });
    r.Then(/the counter is (\d+)/, function (n) {
      assert.equal(this.c, Number(n));
    });
    return r;
  };

  test('parses Background, Outline + Examples, * and But, tags and comments', async () => {
    const f = parseFeature(sample, 'sample.feature');
    assert.equal(f.name, 'Sample');
    assert.equal(f.background.length, 1);
    assert.deepEqual(f.scenarios.map((s) => s.name), ['add 2 [n=2, total=3]', 'add 5 [n=5, total=6]', 'plain']);
    for (const s of f.scenarios) await runScenario(f, s, reg(), async () => ({}));
  });

  test('an undefined step fails the scenario', async () => {
    const f = parseFeature('Feature: X\n  Scenario: y\n    Given something nobody defined\n', 'x.feature');
    await assert.rejects(runScenario(f, f.scenarios[0], reg(), async () => ({})), /Undefined step/);
  });

  test('an ambiguous step fails the scenario', async () => {
    const r = reg();
    r.Then(/the counter is .*/, () => {});
    const f = parseFeature('Feature: X\n  Background:\n    Given a counter at 1\n  Scenario: y\n    Then the counter is 1\n', 'x.feature');
    await assert.rejects(runScenario(f, f.scenarios[0], r, async () => ({})), /Ambiguous step/);
  });

  test('a failing assertion reports the feature line', async () => {
    const f = parseFeature('Feature: X\n  Background:\n    Given a counter at 1\n  Scenario: y\n    Then the counter is 9\n', 'x.feature');
    await assert.rejects(runScenario(f, f.scenarios[0], reg(), async () => ({})), /x\.feature:5/);
  });

  test('malformed features are rejected', () => {
    assert.throws(() => parseFeature('Scenario: no feature\n', 'a'), /before Feature/);
    assert.throws(() => parseFeature('Feature: a\n  Scenario Outline: o\n    Given x <a>\n', 'a'), /no Examples/);
    assert.throws(() => parseFeature('Feature: a\n  Examples:\n', 'a'), /outside a Scenario Outline/);
  });
});
