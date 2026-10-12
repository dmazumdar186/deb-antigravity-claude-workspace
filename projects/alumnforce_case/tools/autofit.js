const { chromium } = require('playwright'); const fs=require('fs');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args:['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + process.cwd() + '/deck.html');
  const zooms = await p.evaluate(() => {
    const out=[];
    document.querySelectorAll('section.slide').forEach((s,i)=>{
      const top=()=>s.getBoundingClientRect().top;
      const foot=s.querySelector('.foot');
      const limit=()=> (foot? foot.getBoundingClientRect().top-top()-6 : 720-16);
      const leafBottom=()=>{ let m=0; s.querySelectorAll('p,li,td,th,pre,h1,h2,h3,.big,.legend,.card,table').forEach(e=>{ if(e.closest('.foot'))return; m=Math.max(m,e.getBoundingClientRect().bottom-top()); }); return m; };
      let z=1.0;
      const setz=v=>s.querySelectorAll(':scope > *:not(.foot)').forEach(e=>e.style.zoom=v.toFixed(2));
      while(leafBottom()>limit() && z>0.6){ z-=0.02; setz(z); }
      // refine upward in 0.01 steps while it still fits
      while(z<1){ const t=+(z+0.01).toFixed(2); setz(t); if(leafBottom()>limit()){ setz(z); break;} z=t; }
      out.push({slide:i+1, zoom:+z.toFixed(2), bottom:Math.round(leafBottom()), limit:Math.round(limit())});
    });
    return out;
  });
  console.log(zooms.map(x=>`${x.slide}: zoom ${x.zoom} bottom ${x.bottom}/${x.limit}`).join('\n'));
  // bake into html
  let html=fs.readFileSync('deck.html','utf8');
  html=html.replace(/\/\*autofit\*\/[\s\S]*?(?=<\/style>)/,'').replace(/ data-zoom="[0-9.]+"/g,'');
  const secs=html.split(/(?=<section class="slide)/); // first chunk is head
  let k=0;
  for(let i=1;i<secs.length;i++){ const z=zooms[k++].zoom; if(z<1){ secs[i]=secs[i].replace(/^<section class="slide([^"]*)"([^>]*)>/, (m,c,rest)=>`<section class="slide${c}"${rest} data-zoom="${z}">`); } }
  html=secs.join('');
  html=html.replace('</style>', `/*autofit*/\n${zooms.filter(z=>z.zoom<1).map(z=>`section[data-zoom="${z.zoom}"] > *:not(.foot){zoom:${z.zoom}}`).join('\n')}\n</style>`);
  fs.writeFileSync('deck.html',html);
  await b.close();
})();
