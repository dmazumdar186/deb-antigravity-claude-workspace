const {chromium}=require('playwright');const U='https://asset-voyages-demo.debanjan186.workers.dev';
(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto(U+'/congres/congres-europeen-de-cardiologie-cg-0101');await p.waitForTimeout(4000);
const o={name:'Zoé Dbg (exemple)',email:`dbg${Date.now()%1e5}@example.com`,phone:'0102030405',departure_city:'Toulouse',passengers:'3',message:process.argv[2]||'hello'};
for(const[k,v]of Object.entries(o))await p.fill(`[name=${k}]`,v);await p.check('#f-consent');await p.click('button:has-text("Envoyer la demande")');await p.waitForLoadState();
const t=await p.evaluate(()=>document.body.innerText);console.log(p.url());console.log(t.slice(0,1500));
console.log(await p.evaluate(()=>[...document.querySelectorAll('[aria-invalid=true]')].map(e=>e.name)));
const w=await p.$('#f-web');if(w)console.log('honeypot box',JSON.stringify(await w.boundingBox()),await w.isVisible());await b.close()})();
