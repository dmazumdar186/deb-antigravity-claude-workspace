(() => {
'use strict';
const root=document.documentElement;
const $=(s,c=document)=>c?c.querySelector(s):null;
const $$=(s,c=document)=>c?Array.from(c.querySelectorAll(s)):[];
const t=k=>window.JeevanaI18n?window.JeevanaI18n.t(k):k;
const motion=matchMedia('(prefers-reduced-motion: reduce)');
const desktop=matchMedia('(min-width: 761px) and (orientation: landscape)');
root.classList.add('has-js');
$$('[data-year]').forEach(el=>{el.textContent=new Date().getFullYear();});
const reveals=$$('[data-reveal]');
const show=(el,past=false)=>{if(past)el.classList.add('is-past');el.classList.add('is-visible');};
if('IntersectionObserver' in window&&!motion.matches){
 const observer=new IntersectionObserver(entries=>entries.forEach(e=>{
  if(e.isIntersecting||e.boundingClientRect.top<0){show(e.target,e.boundingClientRect.bottom<0);observer.unobserve(e.target);}
 }),{threshold:.06,rootMargin:'0px 0px -4% 0px'});
 reveals.forEach(el=>observer.observe(el));
}else reveals.forEach(el=>show(el));
const minis=$$('.mini__f');
function fillMinis(){minis.forEach(el=>{el.style.strokeDashoffset='0';});}
if(motion.matches||!('IntersectionObserver' in window))fillMinis();
if('IntersectionObserver' in window){
 const ratios=new WeakMap();
 const observer=new IntersectionObserver(entries=>entries.forEach(e=>{
  const ratio=Math.max(ratios.get(e.target)||0,e.intersectionRatio);
  ratios.set(e.target,ratio);
  const ring=$('.mini__f',e.target);
  if(ring)ring.style.strokeDashoffset=motion.matches?'0':String(100*(1-ratio));
 }),{threshold:Array.from({length:21},(_,n)=>n/20)});
 $$('.section-heading').forEach(el=>observer.observe(el));
}
const header=$('.bar, .site-header');
const progress=$('[data-page-progress]');
const photos=$$('[data-parallax]');
let pageFrame=0;
function paintPage(){
 pageFrame=0;
 if(header)header.classList.toggle('is-scrolled',scrollY>80);
 const span=root.scrollHeight-innerHeight;
 if(progress)progress.style.transform='scaleX('+(span>0?Math.min(1,scrollY/span):0)+')';
 reveals.forEach(el=>{if(!el.classList.contains('is-visible')&&el.getBoundingClientRect().top<0)show(el,true);});
 photos.forEach(el=>{
  if(motion.matches||!desktop.matches){el.style.transform='';return;}
  const rect=(el.parentElement||el).getBoundingClientRect();
  if(rect.bottom<0||rect.top>innerHeight)return;
  const p=Math.max(-1,Math.min(1,(rect.top+rect.height/2-innerHeight/2)/innerHeight));
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
document.addEventListener('click',event=>{
 if(!(event.target instanceof Element))return;
 const el=event.target.closest('[data-event]');
 if(el)eventCount(el.dataset.event);
 const format=event.target.closest('[data-format]');
 const select=$('#reg-class');
 if(format&&select){select.value=format.dataset.format;select.dispatchEvent(new Event('change',{bubbles:true}));}
});
function initStrip(){
 const track=$('[data-strip]');
 const cards=$$('article.card',track);
 if(!track||!cards.length)return {refresh:()=>{}};
 const arcs=$$('.twelve .arc[data-n]');
 const centre=$('.twelve--strip .centre');
 const previous=$('[data-prev]'),next=$('[data-next]'),play=$('[data-play]');
 const label=$('[data-play-label]'),live=$('[data-sequence-status]');
 const fill=$('[data-position-fill]'),current=$('[data-cur]');
 let active=0,requested=false,hovered=false,focused=false,visible=false;
 let timer=0,frame=0,scrollEnd=0,resizeTimer=0,pointer=null;
 function announce(){
  const title=$('h3',cards[active]);
  if(live&&title)live.textContent=t('breathCount').replace('{n}',active+1)+': '+title.textContent+'. '+t('s'+(active+1)+'Breath')+'.';
 }
 function setActive(index){
  active=index;
  cards.forEach((card,n)=>{card.classList.toggle('is-active',n===index);if(n===index)card.setAttribute('aria-current','step');else card.removeAttribute('aria-current');});
  arcs.forEach(arc=>arc.classList.toggle('on',Number(arc.dataset.n)===index+1));
  root.dataset.position=String(index+1);
  if(fill)fill.setAttribute('stroke-dashoffset',String(11-index));
  if(current)current.textContent=String(index+1).padStart(2,'0');
  if(previous)previous.disabled=index===0;
  if(next)next.disabled=index===cards.length-1;
  if(centre){
   if(motion.matches)centre.style.transform='scale(1)';
   else if(index!==5)centre.style.transform=[1,3,6,8,10].includes(index)?'scale(1.04)':'scale(1)';
  }
  announce();
 }
 function readCentre(){
  frame=0;
  const middle=track.scrollLeft+track.clientWidth/2;
  let nearest=0,distance=Infinity;
  cards.forEach((card,n)=>{const d=Math.abs(card.offsetLeft+card.offsetWidth/2-middle);if(d<distance){distance=d;nearest=n;}});
  if(nearest!==active)setActive(nearest);
 }
 function go(index,instant=false){
  const n=Math.max(0,Math.min(cards.length-1,Math.round(Number(index)||0)));
  const card=cards[n];
  track.scrollTo({left:card.offsetLeft-(track.clientWidth-card.offsetWidth)/2,behavior:instant||motion.matches?'instant':'smooth'});
  if(instant||motion.matches)setActive(n);
 }
 function schedule(){
  clearTimeout(timer);
  if(!requested||motion.matches||hovered||focused||!visible||document.hidden||pointer)return;
  timer=setTimeout(()=>{
   if(active===cards.length-1){requested=false;updatePlay();return;}
   go(active+1);schedule();
  },4000);
 }
 function updatePlay(){
  if(play){play.disabled=motion.matches;play.setAttribute('aria-pressed',String(requested));const symbol=$('.play-symbol',play);if(symbol)symbol.textContent=requested?'Ⅱ':'▷';}
  const key=motion.matches?'motionOff':requested?'pauseSequence':'playSequence';
  if(label){label.dataset.i18n=key;label.textContent=t(key);}
  if(live)live.setAttribute('aria-live',requested?'off':'polite');
  schedule();
 }
 function stop(){requested=false;updatePlay();}
 if(previous)previous.addEventListener('click',()=>{stop();go(active-1);});
 if(next)next.addEventListener('click',()=>{stop();go(active+1);});
 if(play)play.addEventListener('click',()=>{if(motion.matches)return;requested=!requested;if(requested&&active===cards.length-1)go(0,true);updatePlay();});
 track.addEventListener('keydown',event=>{
  const keys={ArrowRight:active+1,ArrowLeft:active-1,Home:0,End:cards.length-1};
  if(!(event.key in keys))return;
  event.preventDefault();stop();go(keys[event.key]);
 });
 track.addEventListener('scroll',()=>{if(!frame)frame=requestAnimationFrame(readCentre);clearTimeout(scrollEnd);scrollEnd=setTimeout(schedule,160);},{passive:true});
 track.addEventListener('pointerenter',event=>{if(event.pointerType==='mouse'){hovered=true;schedule();}});
 track.addEventListener('pointerleave',()=>{hovered=false;schedule();});
 track.addEventListener('focusin',()=>{focused=true;schedule();});
 track.addEventListener('focusout',event=>{if(!track.contains(event.relatedTarget)){focused=false;schedule();}});
 track.addEventListener('pointerdown',event=>{
  if(event.pointerType!=='mouse'||event.button!==0){stop();return;}
  pointer={id:event.pointerId,x:event.clientX,left:track.scrollLeft,dragging:false};stop();
 });
 track.addEventListener('pointermove',event=>{
  if(!pointer||event.pointerId!==pointer.id)return;
  const delta=event.clientX-pointer.x;
  if(!pointer.dragging&&Math.abs(delta)>6){pointer.dragging=true;track.classList.add('is-dragging');track.setPointerCapture(event.pointerId);}
  if(pointer.dragging){event.preventDefault();track.scrollLeft=pointer.left-delta;}
 });
 function endDrag(event){
  if(!pointer||(event.pointerId!==undefined&&event.pointerId!==pointer.id))return;
  const {id,dragging}=pointer;pointer=null;track.classList.remove('is-dragging');
  if(track.hasPointerCapture(id))track.releasePointerCapture(id);
  if(dragging){readCentre();go(active);}schedule();
 }
 addEventListener('pointerup',endDrag);
 track.addEventListener('pointercancel',endDrag);
 track.addEventListener('lostpointercapture',endDrag);
 if('IntersectionObserver' in window)new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;schedule();},{threshold:.15}).observe(track);
 else visible=true;
 document.addEventListener('visibilitychange',schedule);
 addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>go(active,true),120);});
 window.JV_strip={cur:()=>active,playing:()=>requested,go};
 setActive(0);updatePlay();
 return {refresh:()=>{if(motion.matches)requested=false;setActive(active);updatePlay();}};
}
const strip=initStrip();
const errors={bad_name:'errorName',bad_email:'errorEmail',bad_phone:'errorPhone',consent_required:'errorConsent',rate_limited:'errorRate'};
const forms=$$('[data-form]');
forms.forEach(form=>{
 const fields=$('[data-fields]',form),button=$('button[type=submit]',form),label=$('[data-submit-label]',form),status=$('[data-err]',form);
 if(!status||!button)return;
 form.noValidate=true;
 function fail(key,input){status.dataset.i18n=key;status.textContent=t(key);if(input){input.setAttribute('aria-invalid','true');input.focus();}else status.focus();}
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(form.dataset.pending==='true')return;
  $$('[aria-invalid]',form).forEach(el=>el.removeAttribute('aria-invalid'));
  const get=name=>form.elements.namedItem(name);
  const data=Object.fromEntries(new FormData(form).entries());
  const kind=form.dataset.form;
  data.email=String(data.email||'').trim().toLowerCase();data.phone=String(data.phone||'').trim();
  if(kind==='register'){data.name=String(data.name||'').trim();if(!data.name){fail('errorName',get('name'));return;}}
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)){fail('errorEmail',get('email'));return;}
  if(data.phone&&!/^[+\d][\d\s().-]{5,39}$/.test(data.phone)){fail('errorPhone',get('phone'));return;}
  const consent=get('consent');
  if(!consent||!consent.checked){fail('errorConsent',consent);return;}
  if(!form.checkValidity()){fail('errorFields');return;}
  data.consent=true;data.website=String(data.website||'');data.lang=root.lang==='fr'?'fr':'en';data.source_url=location.href.slice(0,300);
  if(kind==='subscribe')data.source='footer';
  delete status.dataset.i18n;status.textContent='';form.dataset.pending='true';form.setAttribute('aria-busy','true');
  if(fields)fields.disabled=true;button.disabled=true;
  if(label){delete label.dataset.i18n;label.textContent=t('sending');}
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
  try{
   const response=await fetch('/api/'+kind,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(data),credentials:'same-origin',signal:controller.signal});
   const result=await response.json().catch(()=>({}));
   if(!response.ok||result.ok!==true){fail(response.status===429?'errorRate':errors[result.error]||'errorServer');return;}
   const success=$('[data-ok='+kind+']');
   if(success){form.hidden=true;success.hidden=false;success.focus({preventScroll:true});}
   if(kind==='subscribe')eventCount('subscribe');
  }catch(_){fail('errorNetwork');}
  finally{
   clearTimeout(timeout);if(fields)fields.disabled=false;button.disabled=false;delete form.dataset.pending;form.removeAttribute('aria-busy');
   if(label){const key=kind==='register'?'sendRegistration':'subscribe';label.dataset.i18n=key;label.textContent=t(key);}
  }
 });
});
document.addEventListener('jeevana:language',()=>{
 strip.refresh();forms.forEach(form=>{if(form.dataset.pending==='true'){const label=$('[data-submit-label]',form);if(label)label.textContent=t('sending');}});queuePage();
});
function motionChanged(){if(motion.matches){reveals.forEach(el=>show(el,true));fillMinis();}strip.refresh();queuePage();}
if(motion.addEventListener)motion.addEventListener('change',motionChanged);else motion.addListener(motionChanged);
if(desktop.addEventListener)desktop.addEventListener('change',queuePage);
})();
