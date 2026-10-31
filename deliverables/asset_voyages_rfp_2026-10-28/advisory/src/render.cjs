const {chromium}=require('playwright');const path=require('path');
(async()=>{const b=await chromium.launch();const p=await b.newPage();
const n='ASSET_Voyages_Technical_Advisory_Pack_2026-10-31';
await p.goto('file://'+path.resolve(__dirname,'..',n+'.html'),{waitUntil:'load'});
const s='font-family:Inter,sans-serif;font-size:7.5pt;color:#667;width:100%;padding:0 16mm;display:flex;justify-content:space-between';
await p.pdf({path:path.resolve(__dirname,'..',n+'.pdf'),format:'A4',printBackground:true,margin:{top:'16mm',bottom:'16mm',left:'16mm',right:'16mm'},displayHeaderFooter:true,
headerTemplate:`<div style="${s}"><span>ProdCraft · ASSET Voyages Technical Advisory Pack</span><span>Restricted · 31 Oct 2026</span></div>`,
footerTemplate:`<div style="${s}"><span>v1.0</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`});
await b.close();})();
