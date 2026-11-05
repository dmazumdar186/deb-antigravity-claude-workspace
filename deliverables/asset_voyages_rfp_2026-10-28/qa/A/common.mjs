// Shared helpers for qa/A integration, perf and monkey scripts (Option A, WordPress Playground).
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const require = createRequire('/home/user/deb-antigravity-claude-workspace/deliverables/asset_voyages_rfp_2026-10-28/wp_demo/tests/');
export const { chromium, devices } = require('playwright');
export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const LOGS = path.join(HERE, 'logs');
fs.mkdirSync(LOGS, { recursive: true });
export const BASE = process.env.WP_BASE || 'http://127.0.0.1:9403';
export const USERS = {
  admin: ['admin', 'password'],
  direction: ['direction', 'demo-asset'],
  equipe: ['equipe', 'demo-asset'],
  contributeur: ['contributeur', 'demo-asset'],
};
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function login(page, role) {
  const [user, pass] = USERS[role];
  await page.goto(BASE + '/wp-login.php');
  await page.fill('#user_login', user);
  await page.fill('#user_pass', pass);
  await Promise.all([page.waitForURL(/wp-admin/, { timeout: 60000 }), page.click('#wp-submit')]);
  await page.waitForLoadState('load');
}

export async function asRole(browser, role, opts = {}) {
  const ctx = await browser.newContext({ baseURL: BASE, locale: 'fr-FR', viewport: { width: 1440, height: 900 }, ...opts });
  const page = await ctx.newPage();
  if (role) await login(page, role);
  return { ctx, page };
}

export function launch() {
  return chromium.launch({ args: ['--no-sandbox'] });
}

export function pct(arr, p) {
  const s = [...arr].sort((a, b) => a - b);
  if (!s.length) return null;
  return s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)];
}
export const median = (a) => pct(a, 50);
