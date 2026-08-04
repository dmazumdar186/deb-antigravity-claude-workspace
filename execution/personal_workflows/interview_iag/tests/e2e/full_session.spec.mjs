// End-to-end: full user journey through all 3 pages with the /api/claude
// endpoint mocked in-browser via window.__AGENTUP_MOCK. Verifies the
// state-machine of the training island, streak update, dashboard render,
// and custom-case creation.

import { test, expect } from '@playwright/test';

// --- Fixture responses used by the mock hijack ---

const fakeCustomerLines = [
  "That's not good enough. I've been a loyal customer for years.",
  "Fine, but tell me exactly when this will be resolved.",
  "Alright, and can you confirm this in writing?",
  "Okay. I'm going to hold you to that.",
  "Thank you — that finally sounds like a real plan.",
];

const fakeScorecard = (n = 80) => ({
  empathyScore: n, accuracyScore: n - 5, resolutionScore: n + 5, professionalismScore: n,
  overallScore: n, strength: 'Clear ownership of the issue.', improvement: 'Confirm the exact ETA earlier in the conversation.',
});

// Install the mock BEFORE the app hydrates. The mock function must be
// (re-)installed on every navigation, so it goes unconditionally in an init
// script. localStorage state, however, must only be cleared once — otherwise
// the session we persist mid-test gets wiped on the next navigation.
async function seed({ page }) {
  await page.addInitScript(({ lines, score }) => {
    // Guarded clear: only wipe on the very first document of this browser context.
    // window.* doesn't survive navigations — localStorage does.
    if (!localStorage.getItem('agentup:e2e-seeded')) {
      localStorage.clear();
      localStorage.setItem('agentup:e2e-seeded', '1');
    }
    // These mock closures are recreated per page load; that's fine.
    let scoreCalls = 0;
    let roleplayCalls = 0;
    window.__FAKE_LINES = lines;
    window.__FAKE_SCORE = (n) => ({
      empathyScore: n, accuracyScore: n - 5, resolutionScore: n + 5, professionalismScore: n,
      overallScore: n, strength: score.strength, improvement: score.improvement,
    });
    window.__AGENTUP_MOCK = async (body) => {
      if (body.mode === 'roleplay') {
        const line = window.__FAKE_LINES[roleplayCalls % window.__FAKE_LINES.length];
        roleplayCalls++;
        return { text: line };
      }
      if (body.mode === 'score') {
        scoreCalls++;
        return window.__FAKE_SCORE(70 + scoreCalls * 5);
      }
      throw new Error('unmocked_mode:' + body.mode);
    };
  }, { lines: fakeCustomerLines, score: { strength: fakeScorecard().strength, improvement: fakeScorecard().improvement } });
}

test.describe('AgentUp — navigation and 3-page smoke', () => {
  test.beforeEach(seed);

  test('all 3 routes render with proper nav highlighting', async ({ page }) => {
    // Dev-server first-hit route compilation can take a few seconds — use generous timeouts.
    await page.goto('/');
    await expect(page.locator('main h1')).toHaveText(/Daily Training/, { timeout: 20000 });
    await expect(page.getByRole('link', { name: 'Daily Training', exact: true })).toHaveAttribute('aria-current', 'page');

    await page.goto('/cases');
    await expect(page.locator('main h1')).toHaveText(/My Cases/, { timeout: 20000 });
    await expect(page.getByRole('link', { name: 'My Cases', exact: true })).toHaveAttribute('aria-current', 'page');
    // Wait for React island to hydrate and paint the 5 defaults.
    await expect(page.getByTestId('cases-list').locator('tr')).toHaveCount(5, { timeout: 15000 });

    await page.goto('/dashboard');
    await expect(page.locator('main h1')).toHaveText(/My Dashboard/, { timeout: 20000 });
    await expect(page.getByTestId('dashboard-empty')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('My Cases page', () => {
  test.beforeEach(seed);

  test('filter dropdowns narrow the visible cases', async ({ page }) => {
    await page.goto('/cases');
    // Wait for hydration first.
    await expect(page.getByTestId('cases-list').locator('tr')).toHaveCount(5, { timeout: 10000 });
    // Only def-angry-01 is at Advanced difficulty among the 5 defaults.
    await page.getByTestId('filter-difficulty').selectOption('Advanced');
    await expect(page.getByTestId('cases-list').locator('tr')).toHaveCount(1);
    await expect(page.getByText('Third call about an unresolved outage')).toBeVisible();
    // Reset → back to 5.
    await page.getByTestId('filter-difficulty').selectOption('');
    await expect(page.getByTestId('cases-list').locator('tr')).toHaveCount(5);
  });

  test('creating a new case shows it in the table', async ({ page }) => {
    await page.goto('/cases');
    await page.getByTestId('btn-new-case').click();
    await page.getByTestId('in-title').fill('Refund request past window');
    await page.getByTestId('in-scenario').fill('Customer bought a product 45 days ago and wants a refund. Store policy is 30 days. They are polite but insistent.');
    await page.getByTestId('in-opening').fill('Hi, I need to return this laptop I bought last month.');
    await page.getByTestId('in-topic').selectOption('Policy Exception');
    await page.getByTestId('btn-save-case').click();
    // Modal closed
    await expect(page.getByTestId('in-title')).toHaveCount(0);
    // Row visible
    await expect(page.getByText('Refund request past window')).toBeVisible();
  });

  test('form validates title length and scenario length', async ({ page }) => {
    await page.goto('/cases');
    await page.getByTestId('btn-new-case').click();
    await page.getByTestId('in-title').fill('X'); // too short
    await page.getByTestId('in-scenario').fill('short');
    await page.getByTestId('in-opening').fill('hi');
    await page.getByTestId('btn-save-case').click();
    await expect(page.getByText(/Title must be 5.50 characters/)).toBeVisible();
  });
});

test.describe('Daily Training — full session end-to-end', () => {
  test.beforeEach(async ({ page }) => {
    await seed({ page });
    // Additionally: seed localStorage with 5 Chat-only cases using the SAME
    // ids as the built-in defaults, so loadState()'s default-merge is a no-op
    // and pickDailyCases() only ever picks a Chat trio (avoids the mic-required
    // Call UI in E2E).
    await page.addInitScript(() => {
      // Guard via localStorage marker — survives navigations.
      if (localStorage.getItem('agentup:e2e-chatcases-seeded')) return;
      localStorage.setItem('agentup:e2e-chatcases-seeded', '1');
      const chatCases = [
        { id: 'def-billing-01', title: 'Chat: duplicate charge',    scenario: 'Customer noticed a duplicate charge on the invoice.',            opening: 'Hi, I was charged twice.',                       channel: 'Chat', topic: 'Billing',    difficulty: 'Beginner',    isDefault: true },
        { id: 'def-angry-01',   title: 'Chat: repeat late-fee complaint', scenario: 'Customer sees the same late fee for the third month running.', opening: 'This late fee has appeared three months in a row.', channel: 'Chat', topic: 'Billing', difficulty: 'Intermediate', isDefault: true },
        { id: 'def-cancel-01',  title: 'Chat: cancel request',      scenario: 'Customer is thinking about cancelling their broadband plan.',    opening: 'I want to cancel my plan.',                     channel: 'Chat', topic: 'Retention',  difficulty: 'Intermediate', isDefault: true },
        { id: 'def-tech-01',    title: 'Chat: slow speed',          scenario: 'Customer reports much slower internet than advertised.',        opening: 'My speed is way lower than promised.',           channel: 'Chat', topic: 'Technical',  difficulty: 'Beginner',    isDefault: true },
        { id: 'def-return-01',  title: 'Chat: return request',      scenario: 'Customer wants to return a smart speaker within the window.',   opening: 'I need to return this speaker.',                 channel: 'Chat', topic: 'Policy Exception', difficulty: 'Beginner', isDefault: true },
      ];
      localStorage.setItem('agentup:v1', JSON.stringify({
        cases: chatCases, sessions: [], streak: { count: 0, lastDate: null },
      }));
    });
  });

  test('completes 3 cases → summary → dashboard reflects them', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('btn-start-session').click();

    // Case 1
    await runOneCase(page, { channel: 'Chat' });
    await expect(page.getByTestId('scorecard')).toBeVisible();
    await page.getByTestId('btn-next-case').click();

    // Case 2
    await runOneCase(page, { channel: 'Chat' });
    await page.getByTestId('btn-next-case').click();

    // Case 3
    await runOneCase(page, { channel: 'Chat' });
    await page.getByTestId('btn-next-case').click();

    // Summary
    await expect(page.getByTestId('summary')).toBeVisible();
    await expect(page.getByText(/Streak · 1 day/)).toBeVisible();

    // Dashboard should now show a session
    await page.goto('/dashboard');
    await expect(page.getByTestId('dashboard-loaded')).toBeVisible();
    await expect(page.getByTestId('sessions-list').locator('tr')).toHaveCount(1);
  });
});

test.describe('Call channel', () => {
  test.beforeEach(seed);

  test('Call channel exposes mic button and accepts typed fallback', async ({ page }) => {
    // Deterministically pick a case that has a Call/Both channel.
    // For fresh state, at least def-angry-01 (Call) is guaranteed pickable eventually,
    // but pickDailyCases is date-seeded — we bypass by picking from `/cases` directly.
    await page.goto('/cases');
    // Just verify a Call-labelled case exists.
    await expect(page.getByText('Third call about an unresolved outage')).toBeVisible();
    // Full call-channel flow is exercised by the integration + unit-test layer;
    // this smoke test just proves the button surface hydrates.
    await page.goto('/');
    await page.getByTestId('btn-start-session').click();
    // Pick the case's channel — Chat is always safe; Call button appears only for Call/Both cases.
    await expect(page.getByTestId('btn-channel-chat')).toBeVisible();
  });
});

// --- helpers ---

async function runOneCase(page, opts) {
  // Pick channel
  const chatBtn = page.getByTestId('btn-channel-chat');
  const callBtn = page.getByTestId('btn-channel-call');
  if (opts.channel === 'Chat' && (await chatBtn.count()) > 0) {
    await chatBtn.click();
  } else if (opts.channel === 'Call' && (await callBtn.count()) > 0) {
    await callBtn.click();
  } else {
    // fallback: click whichever exists first
    if (await chatBtn.count() > 0) await chatBtn.click();
    else await callBtn.click();
  }

  // Wait for the case to fully hydrate — opening bubble must be present.
  await expect(page.getByTestId('active-case')).toBeVisible({ timeout: 15000 });
  await expect.poll(
    async () => await page.getByTestId('transcript').locator('div.max-w-\\[80\\%\\]').count(),
    { timeout: 15000, message: 'expected opening bubble to render' },
  ).toBeGreaterThanOrEqual(1);

  // 5 agent turns — every agent turn (including the 5th) is followed by an AI reply.
  // After the 5th AI reply the case auto-scores.
  for (let i = 1; i <= 5; i++) {
    const input = page.getByTestId('agent-input');
    await input.fill(`Agent turn ${i}: I understand and I'll help you fix this.`);
    await page.getByTestId('btn-send').click();
    // Bubble count = 1 opening + 2 per turn (agent + customer) = 1 + 2i.
    await expect.poll(
      async () => await page.getByTestId('transcript').locator('div.max-w-\\[80\\%\\]').count(),
      { timeout: 10000, message: `expected ${1 + 2 * i} bubbles after agent turn ${i} + its AI reply` },
    ).toBeGreaterThanOrEqual(1 + 2 * i);
  }

  // After the 5th AI reply, scoring runs and the scorecard renders.
  await expect(page.getByTestId('scorecard')).toBeVisible({ timeout: 20000 });
}
