(()=>{
'use strict';
// Reviews page: renders /api/reviews (summary, featured, paginated list) and posts the review form.
// All review text goes in with textContent, never innerHTML.
const $=(s,c=document)=>c.querySelector(s),$$=(s,c=document)=>Array.from(c.querySelectorAll(s));
const t=k=>window.JeevanaI18n?window.JeevanaI18n.t(k):k,lang=()=>document.documentElement.lang==='fr'?'fr':'en',loc=()=>lang()==='fr'?'fr-FR':'en-GB';
const form=$('[data-review-form]');if(!form)return;
const listEl=$('[data-list]'),featEl=$('[data-featured]'),more=$('[data-more]'),status=$('[data-list-status]');
let data=null,offset=0,shown=[],failed=false;
function fmt(template,vars){return String(template).replace(/\{(\w+)\}/g,(_,k)=>vars[k]??'');}
function starText(n){return fmt(t(n===1?'starsOne':'starsMany'),{n});}
function starGlyphs(n){const out=[];for(let i=1;i<=5;i++){const g=document.createElement('span');g.textContent='★';g.className=i<=n?'on':'off';g.setAttribute('aria-hidden','true');out.push(g);}return out;}
function starsSpan(n){const s=document.createElement('span');s.className='stars';s.setAttribute('role','img');s.setAttribute('aria-label',starText(n));s.append(...starGlyphs(n));return s;}
function date(ts){try{return new Date(ts).toLocaleDateString(loc(),{day:'numeric',month:'long',year:'numeric'});}catch(_){return String(ts).slice(0,10);}}
function card(r,featured){
  const li=document.createElement('li');li.className=featured?'review-card review-card--featured':'review-card';
  const fig=document.createElement('figure'),top=document.createElement('div');top.className='review-card__top';top.append(starsSpan(r.rating));
  const time=document.createElement('time');time.dateTime=r.ts;time.textContent=date(r.ts);top.append(time);
  const q=document.createElement('blockquote');if(r.lang)q.lang=r.lang;String(r.text).split(/\n+/).forEach(p=>{const el=document.createElement('p');el.textContent=p;q.append(el);});
  const cap=document.createElement('figcaption');cap.textContent=r.name;fig.append(top,q,cap);li.append(fig);return li;
}
function render(){
  if(failed){status.textContent=t('reviewsLoadError');return;}
  if(!data){status.textContent=t('reviewsLoading');return;}
  const sum=$('[data-summary]');
  if(data.total){
    sum.hidden=false;$('[data-average]').textContent=Number(data.average).toLocaleString(loc(),{minimumFractionDigits:1,maximumFractionDigits:1});
    const as=$('[data-average-stars]');as.replaceChildren(...starGlyphs(Math.round(data.average)));
    $('[data-count]').textContent=fmt(t(data.total===1?'reviewsCountOne':'reviewsCountMany'),{n:data.total,avg:Number(data.average).toLocaleString(loc())});
    status.textContent='';
  }else{sum.hidden=true;status.textContent=t('reviewsEmpty');}
  $('[data-featured-wrap]').hidden=!data.featured.length;featEl.replaceChildren(...data.featured.map(r=>card(r,true)));
  $('[data-all-wrap]').hidden=!shown.length;listEl.replaceChildren(...shown.map(r=>card(r,false)));more.hidden=shown.length>=data.rest_total;
}
async function load(reset){
  if(reset){offset=0;shown=[];}
  try{
    const res=await fetch('/api/reviews?offset='+offset+'&limit=10'+(reset?'&_='+Date.now():''),{headers:{Accept:'application/json'}});
    const out=await res.json();if(!res.ok||!out.ok)throw new Error('http '+res.status);
    failed=false;data=out;shown=shown.concat(out.reviews.filter(r=>!shown.some(s=>s.id===r.id)));offset=out.offset+out.reviews.length;
  }catch(_){if(!data)failed=true;}
  render();
}
more.addEventListener('click',()=>{more.disabled=true;load(false).finally(()=>{more.disabled=false;});});
// Star picker: the radios stay the real control; data-value / data-hover paint the stars up to that one.
const stars=$('[data-star-input]');
$$('input[name=rating]',stars).forEach(i=>i.addEventListener('change',()=>{stars.dataset.value=i.value;}));
$$('label',stars).forEach((l,i)=>{l.addEventListener('mouseenter',()=>{stars.dataset.hover=String(i+1);});l.addEventListener('mouseleave',()=>{delete stars.dataset.hover;});});
const text=$('#rv-text'),count=$('[data-text-count]');
function counter(){const n=text.value.trim().length;count.textContent=n<20?fmt(t('reviewsMinChars'),{n:20-n}):fmt(t('reviewsChars'),{n,max:1200});}
text.addEventListener('input',counter);
const err=$('[data-err]',form),button=$('button[type=submit]',form),label=$('[data-submit-label]',form),fields=$('[data-fields]',form);
function clear(){$$('[aria-invalid]',form).forEach(e=>{e.removeAttribute('aria-invalid');e.removeAttribute('aria-describedby');});delete err.dataset.i18n;err.textContent='';}
function fail(key,name){err.dataset.i18n=key;err.textContent=t(key);const el=name?(name==='rating'?$('#rv-1'):form.elements.namedItem(name)):null;if(el&&el.focus){el.setAttribute('aria-invalid','true');el.setAttribute('aria-describedby',err.id);el.focus();}else err.focus();}
const errors={bad_name:['reviewsErrName','name'],bad_rating:['reviewsErrRating','rating'],bad_text:['reviewsErrText','text'],consent_required:['errorConsent','consent'],rate_limited:['errorRate']};
form.addEventListener('submit',async ev=>{
  ev.preventDefault();if(form.dataset.pending)return;clear();
  const checked=$('input[name=rating]:checked',form);
  const d={rating:checked?Number(checked.value):0,name:String(form.elements.namedItem('name').value||'').trim(),text:String(text.value||'').trim(),consent:form.elements.namedItem('consent').checked,website:String(form.elements.namedItem('website').value||''),lang:lang()};
  if(!(d.rating>=1&&d.rating<=5))return fail('reviewsErrRating','rating');
  if(d.name.length<2)return fail('reviewsErrName','name');
  if(d.text.length<20)return fail('reviewsErrText','text');
  if(!d.consent)return fail('errorConsent','consent');
  form.dataset.pending='1';form.setAttribute('aria-busy','true');button.disabled=true;delete label.dataset.i18n;label.textContent=t('sending');
  const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),15000);
  try{
    const res=await fetch('/api/reviews',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json'},body:JSON.stringify(d),credentials:'same-origin',signal:ctrl.signal});
    const out=await res.json().catch(()=>({}));
    if(!res.ok||out.ok!==true){const e=res.status===429?errors.rate_limited:errors[out.error]||['errorServer'];fail(e[0],e[1]);return;}
    const pub=out.status==='published',ttl=$('[data-review-ok-title]'),body=$('[data-review-ok-body]');
    ttl.dataset.i18n=pub?'reviewsOkTitle':'reviewsPendingTitle';body.dataset.i18n=pub?'reviewsOkBody':'reviewsPendingBody';
    ttl.textContent=t(ttl.dataset.i18n);body.textContent=t(body.dataset.i18n);
    form.hidden=true;const ok=$('[data-review-ok]');ok.hidden=false;ok.focus({preventScroll:true});if(pub)load(true);
  }catch(_){fail('errorNetwork');}
  finally{clearTimeout(timer);button.disabled=false;if(fields)fields.disabled=false;delete form.dataset.pending;form.removeAttribute('aria-busy');label.dataset.i18n='reviewsSubmit';label.textContent=t('reviewsSubmit');}
});
document.addEventListener('jeevana:language',()=>{render();counter();});
counter();render();load(true);
})();
