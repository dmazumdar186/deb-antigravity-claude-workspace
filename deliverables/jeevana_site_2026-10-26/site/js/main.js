(()=>{
'use strict';
const root=document.documentElement,$=(s,c=document)=>c?c.querySelector(s):null,$$=(s,c=document)=>c?Array.from(c.querySelectorAll(s)):[],on=(e,n,f,o)=>{if(e)e.addEventListener(n,f,o);},t=k=>window.JeevanaI18n?window.JeevanaI18n.t(k):k;
const motion=matchMedia('(prefers-reduced-motion: reduce)'),desktop=matchMedia('(min-width:761px) and (orientation:landscape)'),IO='IntersectionObserver'in window;
root.classList.add('has-js');
$$('[data-year]').forEach(e=>e.textContent=String(new Date().getFullYear()));
const reveals=$$('[data-reveal]'),minis=$$('.mini__f');
const show=(e,past=false)=>{e.classList.add('is-visible');if(past)e.classList.add('is-past');};
let rio;
if(IO&&!motion.matches){rio=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting||e.boundingClientRect.top<0){show(e.target,e.boundingClientRect.top<0);rio.unobserve(e.target);} }),{threshold:.01});reveals.forEach(e=>rio.observe(e));}else reveals.forEach(e=>show(e,true));
const fillMinis=()=>minis.forEach(e=>e.style.strokeDashoffset='0');
if(motion.matches||!IO)fillMinis();else{const best=new WeakMap(),observer=new IntersectionObserver(es=>es.forEach(e=>{const r=Math.max(best.get(e.target)||0,e.intersectionRatio);best.set(e.target,r);const ring=$('.mini__f',e.target);if(ring)ring.style.strokeDashoffset=motion.matches||r>.97?'0':String(+(100*(1-r)).toFixed(1));}),{threshold:Array.from({length:21},(_,n)=>n/20)});$$('.section-heading').forEach(e=>observer.observe(e));}
const header=$('.bar'),progress=$('[data-page-progress]'),photos=$$('[data-parallax]');let pageFrame=0,lastY=scrollY;
function paintPage(){pageFrame=0;const y=scrollY,fast=Math.abs(y-lastY)>120;lastY=y;if(header)header.classList.toggle('is-scrolled',y>80);const span=root.scrollHeight-innerHeight;if(progress)progress.style.transform='scaleX('+(span>0?Math.min(1,y/span):0)+')';reveals.forEach(e=>{if(e.classList.contains('is-visible'))return;const r=e.getBoundingClientRect();if(r.top<0||(fast&&r.top<innerHeight)){show(e,true);if(rio)rio.unobserve(e);}});photos.forEach(e=>{if(motion.matches||!desktop.matches){e.style.transform='';return;}const r=e.parentElement.getBoundingClientRect();if(r.bottom<0||r.top>innerHeight)return;const p=Math.max(-1,Math.min(1,(r.top+r.height/2-innerHeight/2)/innerHeight));e.style.transform='translate3d(0,'+(p*12*Number(e.dataset.parallax)).toFixed(2)+'px,0)';});}
const queuePage=()=>{if(!pageFrame)pageFrame=requestAnimationFrame(paintPage);};
addEventListener('scroll',queuePage,{passive:true});addEventListener('resize',queuePage,{passive:true});paintPage();
function eventCount(name){if(!['register_open','whatsapp','instagram','subscribe'].includes(name))return;fetch('/api/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name}),keepalive:true}).catch(()=>{});}
document.addEventListener('click',ev=>{if(!(ev.target instanceof Element))return;const el=ev.target.closest('[data-event]');if(el&&!el.disabled)eventCount(el.dataset.event);const f=ev.target.closest('[data-format]'),sel=$('#reg-class');if(f&&sel){sel.value=f.dataset.format;sel.dispatchEvent(new Event('change',{bubbles:true}));}});
function initStrip(){
const track=$('[data-strip]');if(!track)return{refresh(){}};
const cards=$$('article.card',track);if(!cards.length)return{refresh(){}};
const prev=$('[data-prev]'),next=$('[data-next]'),play=$('[data-play]'),arrows=$('.sequence-arrows'),label=$('[data-play-label]'),live=$('[data-sequence-status]'),fill=$('[data-position-fill]'),counter=$('[data-cur]'),arcs=$$('.twelve .arc[data-n]');
let active=0,intent=0,playing=false,timer=0,frame=0,settle=0,drag=null,visible=true,playHover=false;
const last=cards.length-1,maxScroll=()=>Math.max(0,track.scrollWidth-track.clientWidth);
const position=i=>Math.max(0,Math.min(maxScroll(),cards[i].offsetLeft+cards[i].offsetWidth/2-track.clientWidth/2));
function nearest(){const x=track.scrollLeft;let n=0,d=Infinity;cards.forEach((c,i)=>{const distance=Math.abs(position(i)-x);if(distance<d){d=distance;n=i;}});return n;}
function display(i){if(i===active&&root.dataset.position===String(i+1))return;active=i;cards.forEach((c,n)=>{c.classList.toggle('is-active',i===n);if(i===n)c.setAttribute('aria-current','step');else c.removeAttribute('aria-current');});arcs.forEach(a=>a.classList.toggle('on',Number(a.dataset.n)===i+1));root.dataset.position=String(i+1);if(counter)counter.textContent=String(i+1).padStart(2,'0');if(fill)fill.setAttribute('stroke-dashoffset',String(last-i));if(prev)prev.setAttribute('aria-disabled',String(i===0));if(next)next.setAttribute('aria-disabled',String(i===last));const h=$('h3',cards[i]);if(live&&h)live.textContent=t('breathCount').replace('{n}',i+1)+': '+h.textContent+'. '+t('s'+(i+1)+'Breath')+'.';}
function paint(){frame=0;display(nearest());}
function go(i,instant=false){intent=Math.max(0,Math.min(last,Math.round(Number(i)||0)));track.scrollTo({left:position(intent),behavior:instant||motion.matches?'auto':'smooth'});if(instant||motion.matches)display(nearest());}
function paused(){const focus=document.activeElement;return document.hidden||!visible||!!drag||playHover||track.matches(':hover')||!!(arrows&&arrows.matches(':hover'))||track.contains(focus)||!!(arrows&&arrows.contains(focus));}
function schedule(){clearTimeout(timer);timer=0;if(!playing||motion.matches||paused())return;timer=setTimeout(()=>{timer=0;if(!playing||paused())return;go(active===last?0:active+1);schedule();},4000);}
function playUI(){if(motion.matches)playing=false;if(play){play.disabled=motion.matches;play.setAttribute('aria-pressed',String(playing));const icon=$('.play-symbol',play);if(icon)icon.textContent=playing?'❚❚':'▷';}if(label){const key=motion.matches?'motionOff':playing?'pauseSequence':'playSequence';label.dataset.i18n=key;label.textContent=t(key);}if(live)live.setAttribute('aria-live',playing?'off':'polite');schedule();}
function stop(){playing=false;playUI();}
on(prev,'click',()=>{stop();go(Math.max(0,active-1));});on(next,'click',()=>{stop();go(Math.min(last,active+1));});
on(play,'click',()=>{if(motion.matches)return;playing=!playing;playHover=false;playUI();if(playing){go(active===last?0:active+1);schedule();}else{clearTimeout(timer);timer=0;}});
on(play,'pointerenter',ev=>{if(ev.pointerType==='mouse'&&playing){playHover=true;schedule();}});on(play,'pointerleave',()=>{playHover=false;schedule();});
on(track,'keydown',ev=>{const keys={ArrowRight:Math.max(active,intent)+1,ArrowLeft:Math.min(active,intent)-1,Home:0,End:last};if(!(ev.key in keys))return;ev.preventDefault();stop();go(keys[ev.key]);});
on(track,'scroll',()=>{if(!frame)frame=requestAnimationFrame(paint);clearTimeout(settle);settle=setTimeout(()=>{display(nearest());intent=active;},120);},{passive:true});
[track,arrows].forEach(el=>{on(el,'pointerenter',schedule);on(el,'pointerleave',()=>requestAnimationFrame(schedule));on(el,'focusin',schedule);on(el,'focusout',()=>queueMicrotask(schedule));});
on(track,'dragstart',ev=>ev.preventDefault());on(track,'selectstart',ev=>{if(drag)ev.preventDefault();});
on(track,'pointerdown',ev=>{if(ev.pointerType!=='mouse'||ev.button!==0)return;ev.preventDefault();stop();drag={id:ev.pointerId,x:ev.clientX,left:track.scrollLeft,moved:false};track.classList.add('is-dragging');try{track.setPointerCapture(ev.pointerId);}catch(_){} });
on(track,'pointermove',ev=>{if(!drag||ev.pointerId!==drag.id)return;ev.preventDefault();const delta=ev.clientX-drag.x;if(Math.abs(delta)>3)drag.moved=true;track.scrollLeft=drag.left-delta;});
function endDrag(ev){if(!drag||(ev.pointerId!==undefined&&ev.pointerId!==drag.id))return;const {id,moved}=drag,n=nearest();drag=null;try{if(track.hasPointerCapture(id))track.releasePointerCapture(id);}catch(_){}track.classList.remove('is-dragging');if(moved)go(n);else display(n);schedule();}
on(track,'pointerup',endDrag);on(track,'pointercancel',endDrag);on(track,'lostpointercapture',endDrag);addEventListener('pointerup',endDrag);addEventListener('blur',()=>{if(drag)endDrag({});});
if(IO)new IntersectionObserver(es=>{visible=es.some(e=>e.isIntersecting);schedule();},{threshold:0}).observe(track);
on(document,'visibilitychange',schedule);
let resize=0;addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(()=>go(active,true),120);});
track.scrollLeft=0;root.dataset.position='';display(0);playUI();
window.JV_strip={cur:()=>active,playing:()=>playing,go:i=>go(i)};
return{refresh(){go(active,true);root.dataset.position='';display(active);playUI();}};
}
const strip=initStrip(),errors={bad_name:['errorName','name'],bad_email:['errorEmail','email'],bad_phone:['errorPhone','phone'],consent_required:['errorConsent','consent'],rate_limited:['errorRate']},forms=$$('[data-form]');
forms.forEach(form=>{
const fields=$('[data-fields]',form),button=$('button[type=submit]',form),label=$('[data-submit-label]',form),status=$('[data-err]',form);if(!status||!button)return;form.noValidate=true;const kind=form.dataset.form;
function clear(){$$('[aria-invalid]',form).forEach(e=>{e.removeAttribute('aria-invalid');const d=(e.getAttribute('aria-describedby')||'').split(' ').filter(x=>x&&x!==status.id).join(' ');if(d)e.setAttribute('aria-describedby',d);else e.removeAttribute('aria-describedby');});delete status.dataset.i18n;status.textContent='';}
function fail(key,name){status.dataset.i18n=key;status.textContent=t(key);const input=name?form.elements.namedItem(name):null;if(input&&input.setAttribute){input.setAttribute('aria-invalid','true');if(status.id)input.setAttribute('aria-describedby',((input.getAttribute('aria-describedby')||'')+' '+status.id).trim());input.focus();}else status.focus();}
on(form,'submit',async ev=>{ev.preventDefault();if(form.dataset.pending==='true')return;clear();const data=Object.fromEntries(new FormData(form).entries());data.email=String(data.email||'').trim().toLowerCase();data.phone=String(data.phone||'').trim();if(kind==='register'){data.name=String(data.name||'').trim();if(!data.name){fail('errorName','name');return;}}if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)){fail('errorEmail','email');return;}if(data.phone&&!/^[+\d][\d\s().-]{5,39}$/.test(data.phone)){fail('errorPhone','phone');return;}const consent=form.elements.namedItem('consent');if(!consent||!consent.checked){fail('errorConsent','consent');return;}if(!form.checkValidity()){fail('errorFields');return;}data.consent=true;data.website=String(data.website||'');data.lang=root.lang==='fr'?'fr':'en';data.source_url=location.href.slice(0,300);if(kind==='subscribe')data.source='footer';form.dataset.pending='true';form.setAttribute('aria-busy','true');if(fields)fields.disabled=true;button.disabled=true;if(label){delete label.dataset.i18n;label.textContent=t('sending');}const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
try{const res=await fetch('/api/'+kind,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(data),credentials:'same-origin',signal:controller.signal});const out=await res.json().catch(()=>({}));if(!res.ok||out.ok!==true){if(fields)fields.disabled=false;const error=res.status===429?errors.rate_limited:errors[out.error]||['errorServer'];fail(error[0],error[1]);return;}const ok=$('[data-ok="'+kind+'"]');if(ok){form.hidden=true;ok.hidden=false;ok.focus({preventScroll:true});}}
catch(_){if(fields)fields.disabled=false;fail('errorNetwork');}
finally{clearTimeout(timeout);if(fields)fields.disabled=false;button.disabled=false;delete form.dataset.pending;form.removeAttribute('aria-busy');if(label){const key=kind==='register'?'sendRegistration':'subscribe';label.dataset.i18n=key;label.textContent=t(key);}}});
});
on(document,'jeevana:language',()=>{strip.refresh();forms.forEach(f=>{if(f.dataset.pending==='true'){const l=$('[data-submit-label]',f);if(l)l.textContent=t('sending');}});queuePage();});
function motionChanged(){if(motion.matches){reveals.forEach(e=>show(e,true));fillMinis();}strip.refresh();queuePage();}
if(motion.addEventListener)motion.addEventListener('change',motionChanged);else if(motion.addListener)motion.addListener(motionChanged);if(desktop.addEventListener)desktop.addEventListener('change',queuePage);
})();