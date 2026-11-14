/* Scroll-linked ornaments: the Nataraja line reveal (--p) and the contact scroll unroll (--u).
   Without this file, or with reduced motion, both render complete and static. */
(()=>{
  'use strict';
  const root=document.documentElement;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const scrolls=[...document.querySelectorAll('[data-unroll]')];
  const deities=[...document.querySelectorAll('[data-reveal]')];
  if(!scrolls.length&&!deities.length)return;
  const clamp=v=>v<0?0:v>1?1:v;
  const smooth=t=>t*t*(3-2*t);
  let queued=false;

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
    for(const el of deities){
      const r=el.getBoundingClientRect();
      // starts as the figure enters, complete when its centre reaches mid-viewport
      el.style.setProperty('--p',smooth(clamp((vh-r.top)/(vh*.5+r.height/2))).toFixed(4));
    }
  }
  function queue(){if(!queued){queued=true;requestAnimationFrame(update);}}
  function openFully(el){el.dataset.open='1';el.style.setProperty('--u','1');}
  function setMode(){
    if(reduce.matches){
      root.classList.remove('orn');
      for(const el of [...scrolls,...deities]){el.style.removeProperty('--u');el.style.removeProperty('--p');}
      return;
    }
    root.classList.add('orn');
    update();
  }

  for(const el of scrolls)el.addEventListener('focusin',()=>openFully(el));
  window.addEventListener('scroll',queue,{passive:true});
  window.addEventListener('resize',queue,{passive:true});
  if(reduce.addEventListener)reduce.addEventListener('change',setMode);
  setMode();
})();
