import { chromium } from 'playwright';
export const BASE = process.env.WP_BASE || 'http://127.0.0.1:9402';
export const USERS = { admin:['admin','password'], direction:['direction','demo-asset'], equipe:['equipe','demo-asset'], contributeur:['contributeur','demo-asset'] };
export const CODES = ['DEMO-GME-4KQ7','DEMO-GME-8TZ2','DEMO-GME-3MX9','DEMO-GME-6PL5','DEMO-GME-1RB8'];
export async function ctx(br, w=1440, extra={}) {
  const c = await br.newContext({ baseURL: BASE, locale:'fr-FR', timezoneId:'Europe/Paris', viewport:{width:w,height:w>500?900:844}, deviceScaleFactor:1, isMobile:w<500, hasTouch:w<500, ...extra });
  const p = await c.newPage(); p.errs=[]; p.fails=[];
  p.on('pageerror', e=>p.errs.push(e.message)); p.on('console', m=>{ if(m.type()==='error') p.errs.push(m.text()); });
  p.on('requestfailed', r=>p.fails.push(r.url()+' '+(r.failure()?.errorText||'')));
  return { c, p };
}
export async function login(p, role) {
  const [u,pw]=USERS[role]; await p.goto('/wp-login.php');
  await p.fill('#user_login',u); await p.fill('#user_pass',pw);
  await Promise.all([p.waitForURL(/wp-admin/,{timeout:60000}), p.click('#wp-submit')]); await p.waitForLoadState('load');
}
export function counter(){ const c={n:0,log:[]}; c.click=async(loc,label)=>{c.n++;c.log.push(label||'');await loc.click();}; return c; }
export { chromium };
