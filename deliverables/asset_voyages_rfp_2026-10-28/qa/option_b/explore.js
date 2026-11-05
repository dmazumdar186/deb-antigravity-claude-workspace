const {chromium}=require('playwright');const U='https://asset-voyages-demo.debanjan186.workers.dev';
(async()=>{const b=await chromium.launch();const p=await b.newPage();
const dump=async(t)=>{console.log('=== '+t+' '+p.url());console.log((await p.evaluate(()=>{const o=[];document.querySelectorAll('h1,h2,a,button,label,input,select,textarea,form').forEach(e=>{const n=e.tagName.toLowerCase();if(n=='form')o.push('FORM '+e.method+' '+e.getAttribute('action'));else if(n=='input'||n=='select'||n=='textarea')o.push(n+' name='+e.name+' type='+e.type+(e.required?' REQ':'')+' val='+(e.type=='hidden'?'(h)':e.value.slice(0,30)));else o.push(n+': '+(e.innerText||'').trim().slice(0,60)+(n=='a'?' ->'+e.getAttribute('href'):''))});return o.join('\n')})).slice(0,4000))};
await p.goto(U+'/console');await dump('login');
const user=process.argv[2]||'direction';
await p.fill('input[name=username], input[type=text]',user);await p.fill('input[type=password]','demo-asset');await p.click('button[type=submit]');await p.waitForLoadState();await dump('home');
for(const path of (process.argv[3]||'').split(',').filter(Boolean)){await p.goto(U+path);await dump(path)}
await b.close()})();
