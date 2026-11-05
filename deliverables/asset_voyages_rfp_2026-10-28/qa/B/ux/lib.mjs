import { chromium } from 'playwright';
export const B='https://asset-voyages-demo.debanjan186.workers.dev';
export async function ctx(br, w=1440){ const c=await br.newContext({locale:'fr-FR',timezoneId:'Europe/Paris',viewport:{width:w,height:w>500?900:844},deviceScaleFactor:1, isMobile:w<500, hasTouch:w<500}); const p=await c.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message)); p.on('console',m=>{if(m.type()==='error')errs.push(m.text())}); p.errs=errs; return {c,p}; }
export async function login(p, who){ await p.goto(B+'/console/connexion'); await p.getByLabel('Identifiant').fill(who); await p.getByLabel('Mot de passe').fill('demo-asset'); await p.getByRole('button',{name:'Se connecter'}).click(); await p.waitForURL(/\/console(\?|$|\/$)/); }
export async function logout(p){ await p.getByRole('button',{name:'Se déconnecter'}).first().click(); await p.waitForLoadState(); }
export { chromium };
