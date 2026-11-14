(()=>{
'use strict';
// Contact scroll: unrolls with page scroll. Sets --u (0 rolled .. 1 open) and --sh (sheet height px) on [data-vscroll].
// No JS, reduced motion, or a keyboard focus inside -> fully open (CSS default --u:1).
const el=document.querySelector('[data-vscroll]');if(!el)return;
const sheet=el.querySelector('[data-vscroll-sheet]');if(!sheet)return;
const motion=matchMedia('(prefers-reduced-motion: reduce)');
let raf=0,forced=false;
function measure(){el.style.setProperty('--sh',sheet.offsetHeight+'px');}
function update(){
  raf=0;
  if(motion.matches||forced){el.style.setProperty('--u','1');el.classList.add('is-open');return;}
  const vh=window.innerHeight||document.documentElement.clientHeight;
  const top=el.getBoundingClientRect().top;
  // closed while the scroll's top is in the lower 10% of the screen; fully open once it reaches 30% from the top
  const start=vh*0.9,end=vh*0.3;
  let u=(start-top)/(start-end);u=Math.max(0,Math.min(1,u));
  u=1-Math.pow(1-u,2); // ease-out: unrolls fast, settles gently
  el.style.setProperty('--u',u.toFixed(3));
  el.classList.toggle('is-open',u>=0.999);
}
function queue(){if(!raf)raf=requestAnimationFrame(update);}
el.classList.add('vscroll--js');
measure();update();
addEventListener('scroll',queue,{passive:true});
addEventListener('resize',()=>{measure();queue();});
if('ResizeObserver'in window)new ResizeObserver(()=>{measure();queue();}).observe(sheet);
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(()=>{measure();queue();});
el.addEventListener('focusin',()=>{forced=true;update();});
if(motion.addEventListener)motion.addEventListener('change',queue);
})();
