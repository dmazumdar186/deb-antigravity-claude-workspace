/* Scroll-linked ornaments: the line drawings draw themselves (--p on each [data-draw]), the contact scroll
   unrolls (--u), the chakra figure lights root to crown (.is-lit per point, --k on the axis, .is-aligned) and the
   seven-chakra chart draws its lotuses root to crown (.is-in). Without this file, or with reduced motion, every drawing renders complete and static. */
(()=>{
  'use strict';
  const root=document.documentElement;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const scrolls=[...document.querySelectorAll('[data-unroll]')];
  const draws=[...document.querySelectorAll('[data-draw]')];
  const chakras=[...document.querySelectorAll('[data-chakra]')];
  const charts=[...document.querySelectorAll('[data-chart]')];
  if(!scrolls.length&&!draws.length&&!chakras.length&&!charts.length)return;
  const clamp=v=>v<0?0:v>1?1:v;
  const smooth=t=>t*t*(3-2*t);
  let queued=false;

  // Chakra points, root (index 0) to crown (6): each lights at its threshold of the scene's progress; the axis
  // grows through the same heights, so it reaches each point as that point lights. Progress only ever rises.
  const CK_AT=[.1,.23,.36,.49,.62,.75,.88];
  const CK_Y=[530,484,432,342,268,194,158];
  const ckLen=CK_Y[0]-CK_Y[6];
  const ck=chakras.map(el=>({el,max:0,lit:0,pts:CK_Y.map((_,i)=>[...el.querySelectorAll('.ck-n'+(i+1))])}));
  function axisAt(p){
    if(p<=CK_AT[0])return 0;
    for(let i=1;i<CK_AT.length;i++){
      if(p<CK_AT[i]){const f=(p-CK_AT[i-1])/(CK_AT[i]-CK_AT[i-1]);return (CK_Y[0]-(CK_Y[i-1]+(CK_Y[i]-CK_Y[i-1])*f))/ckLen;}
    }
    return 1;
  }
  function lightChakra(c,vh){
    if(c.el.classList.contains('is-aligned'))return;
    const r=c.el.getBoundingClientRect();
    // begins as the root point (84% down the figure) enters the viewport, complete when its centre reaches 55%
    const p=clamp((vh-r.height*.84-r.top)/Math.max(vh*.2,vh*.45-r.height*.34)); // root enters (top=vh-.84h) -> centre at 55% (top=.55vh-.5h)
    if(p<=c.max)return;
    c.max=p;
    c.el.style.setProperty('--k',axisAt(p).toFixed(4));
    let batch=0;
    while(c.lit<CK_AT.length&&p>=CK_AT[c.lit]){
      // several points crossing in one frame (a fast scroll or a jump) still light one after another
      for(const n of c.pts[c.lit]){n.style.setProperty('--ld',(batch*.16).toFixed(2)+'s');n.classList.add('is-lit');}
      c.lit++;batch++;
    }
    if(p>=.999){c.el.style.setProperty('--k','1');c.el.style.setProperty('--ld',(Math.max(0,batch-1)*.16).toFixed(2)+'s');c.el.classList.add('is-aligned');}
  }
  function resetChakra(c){
    c.max=0;c.lit=0;
    c.el.classList.remove('is-aligned');
    for(const p of ['--k','--ld'])c.el.style.removeProperty(p);
    for(const g of c.pts)for(const n of g){n.classList.remove('is-lit');n.style.removeProperty('--ld');}
  }

  // Sequence each drawing once: the longest outline traces first across most of the draw,
  // the next largest joins early, small details (eyes, flames, ornaments) follow one after another.
  function plan(el){
    const ps=[...el.querySelectorAll('.line .ln')];
    const len=ps.map(p=>{try{return p.getTotalLength();}catch(_){return 0;}});
    const order=ps.map((_,i)=>i).sort((a,b)=>len[b]-len[a]);
    const top=len[order[0]]||1;
    let detail=0;
    order.forEach((i,rank)=>{
      let s,d;
      if(rank===0){s=0;d=.6;}
      else if(len[i]>top*.12){s=.06*rank;d=.5;}
      else{s=Math.min(.5,.34+detail*.035);d=.2;detail++;}
      ps[i].style.setProperty('--s',s.toFixed(3));
      ps[i].style.setProperty('--d',d.toFixed(3));
    });
  }

  function update(){
    queued=false;
    if(!root.classList.contains('orn'))return;
    const vh=window.innerHeight||1;
    for(const el of scrolls){
      if(el.dataset.open==='1')continue;
      const top=el.getBoundingClientRect().top;
      // closed while its top is below 90% of the viewport, fully open once it reaches 40%
      el.style.setProperty('--u',smooth(clamp((vh*.9-top)/(vh*.5))).toFixed(4));
    }
    for(const el of draws){
      if(el.dataset.drawn==='1')continue;
      const r=el.getBoundingClientRect();
      // starts as its top passes 95% of the viewport, complete when its centre reaches about 60%
      const p=smooth(clamp((vh*.95-r.top)/(vh*.35+r.height/2)));
      el.style.setProperty('--p',p.toFixed(4));
      // once drawn it stays drawn: the line never un-draws on the way back up
      if(p>=.999){el.dataset.drawn='1';el.style.setProperty('--p','1');el.classList.add('is-drawn');}
    }
    for(const c of ck)lightChakra(c,vh);
    // the chart draws once, as its list of lotuses rises past 85% of the viewport (or has already been passed)
    for(const el of charts){
      if(el.classList.contains('is-in'))continue;
      const list=el.querySelector('.cchart__list')||el;
      if(list.getBoundingClientRect().top<vh*.85)el.classList.add('is-in');
    }
  }
  function queue(){if(!queued){queued=true;requestAnimationFrame(update);}}
  function openFully(el){el.dataset.open='1';el.style.setProperty('--u','1');}
  function setMode(){
    if(reduce.matches){
      root.classList.remove('orn');
      for(const el of [...scrolls,...draws]){el.style.removeProperty('--u');el.style.removeProperty('--p');el.classList.remove('is-drawn');delete el.dataset.drawn;}
      ck.forEach(resetChakra);
      for(const el of charts)el.classList.remove('is-in');
      return;
    }
    root.classList.add('orn');
    update();
  }

  draws.forEach(plan);
  for(const el of scrolls)el.addEventListener('focusin',()=>openFully(el));
  window.addEventListener('scroll',queue,{passive:true});
  window.addEventListener('resize',queue,{passive:true});
  if(reduce.addEventListener)reduce.addEventListener('change',setMode);
  setMode();
})();
