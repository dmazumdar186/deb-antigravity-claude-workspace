(()=>{
'use strict';
const root=document.documentElement;
const $=(s,c=document)=>c?c.querySelector(s):null;
const $$=(s,c=document)=>c?Array.from(c.querySelectorAll(s)):[];
const t=k=>window.JeevanaI18n?window.JeevanaI18n.t(k):k;
const motion=matchMedia('(prefers-reduced-motion: reduce)'),desktop=matchMedia('(min-width: 761px) and (orientation: landscape)');
const IO='IntersectionObserver' in window;
const on=(el,ev,fn,o)=>{if(el)el.addEventListener(ev,fn,o);};
root.classList.add('has-js');
$$('[data-year]').forEach(el=>{el.textContent=String(new Date().getFullYear());});
let fast=false,fastT=0,lastY=scrollY,rio=null;
const reveals=$$('[data-reveal]');
const show=(el,now)=>{if(now)el.classList.add('is-past');el.classList.add('is-visible');};
if(IO&&!motion.matches){
 rio=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting||e.boundingClientRect.top<0){show(e.target,fast||e.boundingClientRect.bottom<0);rio.unobserve(e.target);}}),{threshold:.01});
 reveals.forEach(el=>rio.observe(el));
}else reveals.forEach(el=>show(el,true));
const minis=$$('.mini__f');
const fillMinis=()=>minis.forEach(el=>{el.style.strokeDashoffset='0';});
if(motion.matches||!IO)fillMinis();
else{
 const best=new WeakMap();
 const mio=new IntersectionObserver(es=>es.forEach(e=>{
  const r=Math.max(best.get(e.target)||0,e.intersectionRatio);best.set(e.target,r);
  const ring=$('.mini__f',e.target);
  if(ring)ring.style.strokeDashoffset=motion.matches||r>.97?'0':String(+(100*(1-r)).toFixed(1));
 }),{threshold:Array.from({length:21},(_,n)=>n/20)});
 $$('.section-heading').forEach(el=>mio.observe(el));
}
const header=$('.bar'),progress=$('[data-page-progress]'),photos=$$('[data-parallax]');
let pageFrame=0;
function paintPage(){
 pageFrame=0;
 const y=scrollY,d=Math.abs(y-lastY);lastY=y;
 if(d>140){fast=true;clearTimeout(fastT);fastT=setTimeout(()=>{fast=false;},400);}
 if(header)header.classList.toggle('is-scrolled',y>80);
 const span=root.scrollHeight-innerHeight,vh=innerHeight;
 if(progress)progress.style.transform='scaleX('+(span>0?Math.min(1,y/span):0)+')';
 reveals.forEach(el=>{
  if(el.classList.contains('is-visible'))return;
  const r=el.getBoundingClientRect();
  if(r.top<0||(fast&&r.top<vh)){show(el,true);if(rio)rio.unobserve(el);}
 });
 photos.forEach(el=>{
  if(motion.matches||!desktop.matches){el.style.transform='';return;}
  const r=(el.parentElement||el).getBoundingClientRect();
  if(r.bottom<0||r.top>vh)return;
  const p=Math.max(-1,Math.min(1,(r.top+r.height/2-vh/2)/vh));
  el.style.transform='translate3d(0,'+(p*12*Number(el.dataset.parallax)).toFixed(2)+'px,0)';
 });
}
const queuePage=()=>{if(!pageFrame)pageFrame=requestAnimationFrame(paintPage);};
addEventListener('scroll',queuePage,{passive:true});
addEventListener('resize',queuePage,{passive:true});
paintPage();
function eventCount(name){
 if(!['register_open','whatsapp','instagram','subscribe'].includes(name))return;
 fetch('/api/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name}),keepalive:true}).catch(()=>{});
}
document.addEventListener('click',ev=>{
 if(!(ev.target instanceof Element))return;
 const el=ev.target.closest('[data-event]');if(el)eventCount(el.dataset.event);
 const f=ev.target.closest('[data-format]'),sel=$('#reg-class');
 if(f&&sel){sel.value=f.dataset.format;sel.dispatchEvent(new Event('change',{bubbles:true}));}
});
function initStrip(){
 const track=$('[data-strip]'),cards=$$('article.card',track);
 if(!track||!cards.length)return{refresh(){}};
 const sec=track.closest('section')||track;
 const arcs=$$('.twelve .arc[data-n]'),centre=$('.twelve--strip .centre');
 const prev=$('[data-prev]'),next=$('[data-next]'),play=$('[data-play]'),arrows=$('.sequence-arrows');
 const label=$('[data-play-label]'),live=$('[data-sequence-status]'),fill=$('[data-position-fill]'),cur=$('[data-cur]');
 const last=cards.length-1;
 let active=-1,playing=false,hover=0,focus=false,visible=!IO,timer=0,raf=0,settle=0,unlock=0,locked=false,drag=null;
 function layout(){
  const w=track.clientWidth,vh=innerHeight,gap=parseFloat(getComputedStyle(track).columnGap)||14;
  const port=matchMedia('(orientation: portrait)').matches;
  const cols=w<600?1:w>=3200?5:w>=1920?4:(port&&w<1100?2:3);
  const peek=cols===1?1.25:cols+.4;
  const cap=.75*Math.max(180,Math.min(vh*.7,vh-(vh<520?150:200)));
  const cw=Math.round(Math.max(140,Math.min((w-gap*cols)/peek,cap)));
  const pad=Math.max(0,Math.round((w-cw)/2));
  track.style.setProperty('--cw',cw+'px');track.style.paddingLeft=pad+'px';track.style.paddingRight=pad+'px';
 }
 const pos=i=>cards[i].offsetLeft+cards[i].offsetWidth/2-track.clientWidth/2;
 function nearest(){
  const mid=track.scrollLeft+track.clientWidth/2;let n=0,d=Infinity;
  cards.forEach((c,i)=>{const x=Math.abs(c.offsetLeft+c.offsetWidth/2-mid);if(x<d){d=x;n=i;}});
  return n;
 }
 function setActive(i){
  if(i===active)return;active=i;
  cards.forEach((c,n)=>{c.classList.toggle('is-active',n===i);if(n===i)c.setAttribute('aria-current','step');else c.removeAttribute('aria-current');});
  arcs.forEach(a=>a.classList.toggle('on',Number(a.dataset.n)===i+1));
  root.dataset.position=String(i+1);
  if(fill)fill.setAttribute('stroke-dashoffset',String(11-i));
  if(cur)cur.textContent=String(i+1).padStart(2,'0');
  if(prev)prev.setAttribute('aria-disabled',String(i===0));
  if(next)next.setAttribute('aria-disabled',String(i===last));
  if(centre&&i!==5)centre.style.transform=!motion.matches&&[1,3,6,8,10].includes(i)?'scale(1.04)':'scale(1)';
  const h=$('h3',cards[i]);
  if(live&&h)live.textContent=t('breathCount').replace('{n}',i+1)+': '+h.textContent+'. '+t('s'+(i+1)+'Breath')+'.';
 }
 function go(i,instant){
  const n=Math.max(0,Math.min(last,Math.round(Number(i)||0)));
  const left=Math.max(0,pos(n));
  setActive(n);
  if(Math.abs(track.scrollLeft-left)<1)return;
  locked=true;clearTimeout(unlock);unlock=setTimeout(()=>{locked=false;},1600);
  track.scrollTo({left,behavior:instant||motion.matches?'auto':'smooth'});
 }
 function schedule(){
  clearTimeout(timer);
  if(!playing||motion.matches||hover||focus||!visible||document.hidden||drag)return;
  timer=setTimeout(()=>{go(active>=last?0:active+1);schedule();},4000);
 }
 function updatePlay(){
  if(play){play.disabled=motion.matches;play.setAttribute('aria-pressed',String(playing));const s=$('.play-symbol',play);if(s)s.textContent=playing?'❚❚':'▷';}
  const k=motion.matches?'motionOff':playing?'pauseSequence':'playSequence';
  if(label){label.dataset.i18n=k;label.textContent=t(k);}
  if(live)live.setAttribute('aria-live',playing?'off':'polite');
  schedule();
 }
 function stop(){if(playing){playing=false;updatePlay();}}
 on(prev,'click',()=>{stop();if(active>0)go(active-1);});
 on(next,'click',()=>{stop();if(active<last)go(active+1);});
 on(play,'click',()=>{if(motion.matches)return;playing=!playing;updatePlay();});
 on(track,'keydown',ev=>{
  const k={ArrowRight:active+1,ArrowLeft:active-1,Home:0,End:last};
  if(!(ev.key in k))return;ev.preventDefault();stop();go(k[ev.key]);
 });
 on(track,'scroll',()=>{
  if(!locked&&!raf)raf=requestAnimationFrame(()=>{raf=0;setActive(nearest());});
  clearTimeout(settle);
  settle=setTimeout(()=>{locked=false;clearTimeout(unlock);if(!drag)setActive(nearest());schedule();},150);
 },{passive:true});
 [track,arrows].forEach(el=>{
  on(el,'pointerenter',ev=>{if(ev.pointerType==='mouse'){hover++;schedule();}});
  on(el,'pointerleave',ev=>{if(ev.pointerType==='mouse'){hover=Math.max(0,hover-1);schedule();}});
  on(el,'focusin',()=>{focus=true;schedule();});
  on(el,'focusout',ev=>{const r=ev.relatedTarget;if(!(r&&(track.contains(r)||(arrows&&arrows.contains(r))))){focus=false;schedule();}});
 });
 on(track,'pointerdown',ev=>{
  if(ev.pointerType!=='mouse'||ev.button!==0){stop();return;}
  drag={id:ev.pointerId,x:ev.clientX,left:track.scrollLeft,moved:false};stop();
 });
 on(track,'pointermove',ev=>{
  if(!drag||ev.pointerId!==drag.id)return;
  const d=ev.clientX-drag.x;
  if(!drag.moved&&Math.abs(d)>6){drag.moved=true;locked=false;track.classList.add('is-dragging');try{track.setPointerCapture(ev.pointerId);}catch(_){}}
  if(drag.moved){ev.preventDefault();track.scrollLeft=drag.left-d;}
 });
 function endDrag(ev){
  if(!drag||(ev.pointerId!==undefined&&ev.pointerId!==drag.id))return;
  const {id,moved}=drag;drag=null;track.classList.remove('is-dragging');
  try{if(track.hasPointerCapture(id))track.releasePointerCapture(id);}catch(_){}
  if(moved){active=-1;go(nearest());}
  schedule();
 }
 addEventListener('pointerup',endDrag);
 on(track,'pointercancel',endDrag);
 on(track,'lostpointercapture',endDrag);
 on(track,'click',ev=>{if(track.classList.contains('is-dragging'))ev.preventDefault();});
 if(IO)new IntersectionObserver(es=>{visible=es[0].isIntersecting;schedule();},{threshold:0}).observe(sec);
 document.addEventListener('visibilitychange',schedule);
 let rt=0;
 addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(()=>{const a=active;layout();active=-1;go(a,true);},120);});
 layout();track.scrollLeft=0;setActive(0);updatePlay();
 window.JV_strip={cur:()=>active,playing:()=>playing,go:i=>go(i)};
 return{refresh(){if(motion.matches)playing=false;layout();const a=active;active=-1;go(a,true);updatePlay();}};
}
const strip=initStrip();
const errs={bad_name:['errorName','name'],bad_email:['errorEmail','email'],bad_phone:['errorPhone','phone'],consent_required:['errorConsent','consent'],rate_limited:['errorRate']};
const forms=$$('[data-form]');
forms.forEach(form=>{
 const fields=$('[data-fields]',form),button=$('button[type=submit]',form),label=$('[data-submit-label]',form),status=$('[data-err]',form);
 if(!status||!button)return;
 form.noValidate=true;
 const kind=form.dataset.form;
 function clear(){
  $$('[aria-invalid]',form).forEach(el=>{
   el.removeAttribute('aria-invalid');
   const d=(el.getAttribute('aria-describedby')||'').split(' ').filter(x=>x&&x!==status.id).join(' ');
   if(d)el.setAttribute('aria-describedby',d);else el.removeAttribute('aria-describedby');
  });
  delete status.dataset.i18n;status.textContent='';
 }
 function fail(key,name){
  status.dataset.i18n=key;status.textContent=t(key);
  const input=name?form.elements.namedItem(name):null;
  if(input&&input.setAttribute){
   input.setAttribute('aria-invalid','true');
   if(status.id)input.setAttribute('aria-describedby',((input.getAttribute('aria-describedby')||'')+' '+status.id).trim());
   input.focus();
  }else status.focus();
 }
 form.addEventListener('submit',async ev=>{
  ev.preventDefault();if(form.dataset.pending==='true')return;
  clear();
  const data=Object.fromEntries(new FormData(form).entries());
  data.email=String(data.email||'').trim().toLowerCase();data.phone=String(data.phone||'').trim();
  if(kind==='register'){data.name=String(data.name||'').trim();if(!data.name){fail('errorName','name');return;}}
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)){fail('errorEmail','email');return;}
  if(data.phone&&!/^[+\d][\d\s().-]{5,39}$/.test(data.phone)){fail('errorPhone','phone');return;}
  const consent=form.elements.namedItem('consent');
  if(!consent||!consent.checked){fail('errorConsent','consent');return;}
  if(!form.checkValidity()){fail('errorFields');return;}
  data.consent=true;data.website=String(data.website||'');data.lang=root.lang==='fr'?'fr':'en';data.source_url=location.href.slice(0,300);
  if(kind==='subscribe')data.source='footer';
  form.dataset.pending='true';form.setAttribute('aria-busy','true');
  if(fields)fields.disabled=true;button.disabled=true;
  if(label){delete label.dataset.i18n;label.textContent=t('sending');}
  const ctl=new AbortController(),to=setTimeout(()=>ctl.abort(),15000);
  try{
   const res=await fetch('/api/'+kind,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(data),credentials:'same-origin',signal:ctl.signal});
   const out=await res.json().catch(()=>({}));
   if(!res.ok||out.ok!==true){
    if(fields)fields.disabled=false;
    const m=res.status===429?errs.rate_limited:errs[out.error]||['errorServer'];
    fail(m[0],m[1]);return;
   }
   const ok=$('[data-ok='+kind+']');
   if(ok){form.hidden=true;ok.hidden=false;ok.focus({preventScroll:true});}
   if(kind==='subscribe')eventCount('subscribe');
  }catch(_){if(fields)fields.disabled=false;fail('errorNetwork');}
  finally{
   clearTimeout(to);if(fields)fields.disabled=false;button.disabled=false;delete form.dataset.pending;form.removeAttribute('aria-busy');
   if(label){const k=kind==='register'?'sendRegistration':'subscribe';label.dataset.i18n=k;label.textContent=t(k);}
  }
 });
});
document.addEventListener('jeevana:language',()=>{
 strip.refresh();
 forms.forEach(f=>{if(f.dataset.pending==='true'){const l=$('[data-submit-label]',f);if(l)l.textContent=t('sending');}});
 queuePage();
});
function motionChanged(){if(motion.matches){reveals.forEach(el=>show(el,true));fillMinis();}strip.refresh();queuePage();}
if(motion.addEventListener)motion.addEventListener('change',motionChanged);else if(motion.addListener)motion.addListener(motionChanged);
if(desktop.addEventListener)desktop.addEventListener('change',queuePage);
})();
