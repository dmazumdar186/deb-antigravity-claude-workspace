/* Scroll-linked ornaments: the line drawings draw themselves (--p on each [data-draw]) and the contact scroll
   unrolls (--u). Without this file, or with reduced motion, every drawing renders complete and static. */
(()=>{
  'use strict';
  const root=document.documentElement;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const scrolls=[...document.querySelectorAll('[data-unroll]')];
  const draws=[...document.querySelectorAll('[data-draw]')];
  if(!scrolls.length&&!draws.length)return;
  const clamp=v=>v<0?0:v>1?1:v;
  const smooth=t=>t*t*(3-2*t);
  let queued=false;

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
  }
  function queue(){if(!queued){queued=true;requestAnimationFrame(update);}}
  function openFully(el){el.dataset.open='1';el.style.setProperty('--u','1');}
  function setMode(){
    if(reduce.matches){
      root.classList.remove('orn');
      for(const el of [...scrolls,...draws]){el.style.removeProperty('--u');el.style.removeProperty('--p');el.classList.remove('is-drawn');delete el.dataset.drawn;}
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
