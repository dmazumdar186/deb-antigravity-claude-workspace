/* GLM 5.3 (z-ai/glm-5.3 via OpenRouter, 2026-10-15) — reviewed by hand; alphas/dot radius raised for legibility on ink; density ×1.6 after eye review. */
window.MISBBackdrop=(function(){'use strict';
function ss(x,a,b){x=(x-a)/(b-a);x=x<0?0:x>1?1:x;return x*x*(3-2*x);}
function mul(a){a=a>>>0;return function(){a=a+0x6D2B79F5|0;var t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
var A='rgba(245,241,234,',ACC='#3F7BBF',TAU=6.2832;
function seine(s){return{x:0.10+0.55*s+0.08*Math.sin(s*3.5),y:0.10+0.22*s+0.05*Math.sin(s*2+1)};}
function saone(s){return{x:0.42+0.08*s+0.02*Math.sin(s*3),y:0.06+0.5*s};}
function rhone(s){return{x:0.82-0.30*s-0.02*Math.sin(s*3),y:0.08+0.5*s};}
function curve(c,f,w,h){var s,g,fst=1;c.beginPath();for(s=0;s<=1.001;s+=0.05){g=f(s);if(fst){c.moveTo(g.x*w,g.y*h);fst=0;}else c.lineTo(g.x*w,g.y*h);}c.stroke();}
function makeDefs(seed){var r=mul(seed>>>0||1),d=[],i,u,s,g;
 for(i=0;i<420;i++){var P,L;
  u=r();
  if(u<0.55){s=r();g=seine(s);P=[g.x+(r()-0.5)*0.05,g.y+(r()-0.5)*0.05];}
  else if(u<0.78){P=[0.74+(r()-0.5)*0.09,0.22+(r()-0.5)*0.09];}
  else{P=[0.06+r()*0.85,0.05+r()*0.55];}
  u=r();
  if(u<0.45){s=r();g=saone(s);L=[g.x+(r()-0.5)*0.04,g.y+(r()-0.5)*0.04];}
  else if(u<0.85){s=r();g=rhone(s);L=[g.x+(r()-0.5)*0.04,g.y+(r()-0.5)*0.04];}
  else if(u<0.94){L=[0.63+(r()-0.5)*0.07,0.62+(r()-0.5)*0.07];}
  else{L=[0.15+r()*0.7,0.2+r()*0.6];}
  d.push({P:P,L:L,rail:(r()*5)|0,a:r(),sp:0.03+r()*0.05,ph:r()*TAU,ph2:r()*TAU,
   amp:1+r()*2,acc:i%37===0,lt:r()<0.03?(r()*4)|0:-1,fs:10+r()*6});
 }
 return d;}
var S=null;
function resize(){var cv=S.cv;S.w=cv.clientWidth||0;S.h=cv.clientHeight||0;
 S.n=Math.max(140,Math.min(420,Math.round(S.w*S.h/5600)||140));
 var d=S.dpr;cv.width=Math.max(1,Math.round(S.w*d));cv.height=Math.max(1,Math.round(S.h*d));
 if(S.ctx)S.ctx.setTransform(d,0,0,d,0,0);}
function onRz(){if(!S)return;resize();if(S.rm)render(0);}
function onVis(){if(!S)return;if(document.hidden)stop();else if(!S.paused&&!S.rm)start();}
function start(){if(!S||S.run||S.rm||!S.ctx)return;S.run=true;S.raf=requestAnimationFrame(tick);}
function tick(ts){if(!S||!S.run)return;if(!document.hidden)render(ts);S.raf=requestAnimationFrame(tick);}
function stop(){if(!S)return;S.run=false;if(S.raf)cancelAnimationFrame(S.raf);S.raf=0;}
function render(t){var c=S&&S.ctx;if(!c||!S.w)return;var w=S.w,h=S.h,p=S.p;t=t||0;
 c.clearRect(0,0,w,h);
 var pw=1-ss(p,0.32,0.46),lw=ss(p,0.56,0.70),jw=1-pw-lw,n=Math.min(S.n,S.defs.length),i,k,d,x,y,X=[],Y=[];
 for(i=0;i<n;i++){d=S.defs[i];
  var al=((d.a+t*0.001*d.sp)%1.35)-0.18;
  var jx=(0.02+d.rail*0.09+al*0.74)*w,jy=(0.05+d.rail*0.12+al*0.88)*h;
  var am=d.amp,dx=Math.sin(t*0.0005+d.ph)*am+Math.sin(t*0.00013+d.ph2)*am*0.8,dy=Math.cos(t*0.0004+d.ph)*am;
  x=pw*d.P[0]*w+jw*jx+lw*d.L[0]*w+dx;y=pw*d.P[1]*h+jw*jy+lw*d.L[1]*h+dy;
  X[i]=x;Y[i]=y;}
 c.lineWidth=1;
 var mw=pw>lw?pw:lw;
 if(mw>0.03){c.strokeStyle=A+'1)';
  for(i=0;i<n;i++)for(k=i+1;k<n;k++){var q=(X[i]-X[k])*(X[i]-X[k])+(Y[i]-Y[k])*(Y[i]-Y[k]);
   if(q<1600){c.globalAlpha=0.05+0.18*mw*(1-Math.sqrt(q)/40);
    c.beginPath();c.moveTo(X[i],Y[i]);c.lineTo(X[k],Y[k]);c.stroke();}}}
 if(pw>0.02){c.globalAlpha=0.26*pw;curve(c,seine,w,h);}
 if(lw>0.02){c.globalAlpha=0.26*lw;curve(c,saone,w,h);curve(c,rhone,w,h);}
 if(jw>0.02){c.globalAlpha=0.04*jw;c.strokeStyle=A+'1)';
  for(k=0;k<5;k++){var bx=0.02+k*0.09,by=0.05+k*0.12;
   c.beginPath();c.moveTo(bx*w,by*h);c.lineTo((bx+0.74)*w,(by+0.88)*h);c.stroke();}}
 for(i=0;i<n;i++){d=S.defs[i];
  if(jw>0.02&&d.lt>=0){var f=Math.sin(t*0.0012+d.ph);
   if(f>0){c.globalAlpha=0.08*jw*f*f*f;c.fillStyle=A+'1)';
    c.font=d.fs+'px Georgia,"Times New Roman",serif';
    c.fillText('MISB'.charAt(d.lt),X[i]+4,Y[i]-4);}}
  c.globalAlpha=0.95*pw+0.7*jw+0.95*lw;
  c.fillStyle=d.acc?ACC:A+'1)';
  c.beginPath();c.arc(X[i],Y[i],d.acc?2:1.4,0,TAU);c.fill();}
 var q=(p-0.74)/0.16;
 if(lw>0.05&&q>0&&q<1){c.globalAlpha=0.3*Math.sin(Math.PI*q)*lw;c.strokeStyle=ACC;
  c.beginPath();c.arc(0.63*w,0.62*h,12+q*46,0,TAU);c.stroke();}
 c.globalAlpha=1;}
return{
 init:function(cv,o){if(!cv||S)return;o=o||{};
  S={cv:cv,ctx:null,w:0,h:0,dpr:Math.min(window.devicePixelRatio||1,o.dpr||1.5),p:0,n:90,
   defs:makeDefs(o.seed||1),run:false,paused:false,rm:!!o.reducedMotion,raf:0};
  try{S.ctx=cv.getContext('2d');}catch(e){S.ctx=null;}
  resize();
  if(S.ctx&&!S.rm&&o.autoplay!==false)start();
  if(window.ResizeObserver){S.ro=new ResizeObserver(function(){onRz();});S.ro.observe(cv);}
  else window.addEventListener('resize',onRz,false);
  document.addEventListener('visibilitychange',onVis,false);
  if(S.rm&&S.ctx)render(0);},
 setProgress:function(p){if(!S)return;S.p=p<0?0:p>1?1:p;if(S.rm&&S.ctx)render(0);},
 render:function(t){if(S&&S.ctx)render(t||0);},
 pause:function(){if(!S)return;S.paused=true;stop();},
 resume:function(){if(!S)return;S.paused=false;if(!document.hidden)start();},
 destroy:function(){if(!S)return;stop();
  if(S.ro){try{S.ro.disconnect();}catch(e){}}
  else window.removeEventListener('resize',onRz,false);
  document.removeEventListener('visibilitychange',onVis,false);S=null;}
};})();
