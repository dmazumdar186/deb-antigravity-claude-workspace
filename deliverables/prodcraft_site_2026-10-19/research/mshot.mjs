import pw from '/opt/node-tools/node_modules/playwright/index.js'; const { chromium, devices } = pw;
const b = await chromium.launch(); const c = await b.newContext({...devices['iPhone 13']}); const p = await c.newPage();
await p.goto('http://localhost:8793/', {waitUntil:'load'}); await p.waitForTimeout(1500);
const v = await p.evaluate(()=>{const v=document.querySelector('video'); return v?{src:v.currentSrc, w:v.videoWidth, h:v.videoHeight, playing:!v.paused}:null});
console.log(JSON.stringify(v)); await p.screenshot({path:'deliverables/prodcraft_site_2026-10-19/screens/mobile-cover-portrait-kling.png'}); await b.close();
