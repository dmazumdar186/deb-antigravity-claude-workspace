const { createRequire } = require('module'); const req = createRequire('/opt/node-tools/node_modules/playwright/package.json'); const { chromium } = req('playwright'); const path=require('path');
(async()=>{const b=await chromium.launch();const out={};
for (const [k,vp] of [['d1440',{width:1440,height:900}],['m390',{width:390,height:844,isMobile:true,hasTouch:true,deviceScaleFactor:2}]]){
 const c=await b.newContext({viewport:{width:vp.width,height:vp.height},isMobile:!!vp.isMobile,hasTouch:!!vp.hasTouch,deviceScaleFactor:vp.deviceScaleFactor||1});const p=await c.newPage();await p.goto('https://gtm-people-redesign.pages.dev/',{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await p.addStyleTag({content:'html{scroll-behavior:auto!important}'});
 
 out[k+'_proofText']=await p.evaluate(()=>document.querySelector('.proof').innerText.replace(/\s+/g,' '));
 await p.evaluate(()=>document.querySelector('#contact').scrollIntoView());await p.waitForTimeout(800);
 await p.fill('#contact [data-demo-form] [name=first]','Sophie');await p.fill('#contact [data-demo-form] [name=last]','Okafor');await p.fill('#contact [data-demo-form] [name=company]','Lumen');await p.fill('#contact [data-demo-form] [name=email]','sophie@lumen.io');
 out[k+'_invalid']=await p.evaluate(()=>[...document.querySelector('#contact [data-demo-form]').elements].filter(e=>!e.checkValidity()).map(e=>e.name+':'+e.validationMessage+':'+e.value));
 await p.click('#contact [data-demo-form] button[type=submit]');await p.waitForTimeout(500);out[k+'_ok']=await p.evaluate(()=>({okHidden:document.querySelector('#contact .form__ok').hidden,disabled:document.querySelector('#contact [data-demo-form] button[type=submit]').disabled}));
 if(k==='d1440'){await p.screenshot({path:path.join(__dirname,'home_d1440_contact_submitted.png')});}
 // newsletter form
 out[k+'_nl']=await p.evaluate(()=>{const f=document.querySelector('#insights form');return f?{action:f.action,demo:f.hasAttribute('data-demo-form'),ok:!!f.querySelector('.form__ok')}:null});
 // header: how many nav items at mobile; menu closed state
 await c.close();}
 console.log(JSON.stringify(out,null,1));await b.close();})();
