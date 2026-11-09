import { chromium } from 'playwright';
const B='https://asset-voyages-demo.debanjan186.workers.dev';
const br=await chromium.launch(); 
async function dump(page,label){
  const items=await page.evaluate(()=>[...document.querySelectorAll('h1,h2,nav a,main a,button,label,input[type=submit],[role=status],.flash,.msg')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+':'+(e.innerText||e.value||'').replace(/\s+/g,' ').trim().slice(0,70)).filter(s=>s.length>3));
  console.log('\n=== '+label+' '+page.url()); console.log([...new Set(items)].join(' | '));
}
const role=process.argv[2];
const ctx=await br.newContext({locale:'fr-FR',timezoneId:'Europe/Paris'}); const p=await ctx.newPage();
if(role==='public'){ await p.goto(B+'/'); await dump(p,'catalogue'); await p.goto(B+'/congres/congres-europeen-de-cardiologie-cg-0101'); await dump(p,'fiche');}
else { await p.goto(B+'/console'); await dump(p,'login');
 await p.getByLabel('Identifiant').fill(role); await p.getByLabel('Mot de passe').fill('demo-asset'); await p.getByRole('button',{name:/connecter/i}).click();
 await dump(p,'home');
 for (const u of process.argv.slice(3)){ await p.goto(B+u); await dump(p,u);} }
await br.close();
