(()=>{
'use strict';
// Scroll-linked ornaments: sets --p (0..1) on each [data-lotus] / [data-nataraja] from its position in the viewport.
// Lotus: petals open. Nataraja: the line drawing draws itself. No JS or reduced motion -> CSS default --p:1 (finished, still).
const els=[...document.querySelectorAll('[data-lotus],[data-nataraja]')];if(!els.length)return;
const motion=matchMedia('(prefers-reduced-motion: reduce)');
let raf=0;
function update(){
  raf=0;
  const vh=window.innerHeight||document.documentElement.clientHeight;
  for(const el of els){
    if(motion.matches){el.style.setProperty('--p','1');el.classList.add('is-open');continue;}
    const r=el.getBoundingClientRect();
    if(r.bottom<-vh||r.top>vh*2)continue; // far off screen: skip work
    // starts as the ornament's centre rises past 95% of the screen; complete at 45%
    const c=r.top+r.height/2,start=vh*0.95,end=vh*0.45;
    let p=(start-c)/(start-end);p=Math.max(0,Math.min(1,p));
    p=1-Math.pow(1-p,3); // ease-out-cubic: unfolds, then settles
    el.style.setProperty('--p',p.toFixed(3));
    el.classList.toggle('is-open',p>=0.999);
  }
}
function queue(){if(!raf)raf=requestAnimationFrame(update);}
update();
addEventListener('scroll',queue,{passive:true});
addEventListener('resize',queue);
if(motion.addEventListener)motion.addEventListener('change',queue);
})();
