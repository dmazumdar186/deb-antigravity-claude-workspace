(function(){'use strict';
function mul(a){return function(){a|=0;a=a+0x6D2B79F5|0;var t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
var W=window,rAF=W.requestAnimationFrame,cObs=W.ResizeObserver;
var API=function(){
var cv,ctx,dpr=1.5,seed=1,rm=false,auto=true,running=false,raf=0,N=0,pts=[],cw=0,ch=0,p=0,letters=[],ro=null,tm=0;
function ln(a,b,m,n){ctx.beginPath();ctx.moveTo(a,b);ctx.lineTo(m,n);ctx.stroke()}
function ease(t){return t<0?0:t>1?1:t*t*(3-2*t)}
function seg(a,b,t){return a+(b-a)*ease(t)}
function build(){
var r=mul(seed),i,area=cw*ch;
N=Math.max(90,Math.min(260,Math.round(area/9000)));
pts=[];for(i=0;i<N;i++)pts.push({x:r(),y:r(),a:r()*6.28,s:.2+r()*.8,o:r()*6.28,k:r()});
// figure1: loose map shape (offset blob) with cluster
var c1x=.32,c1y=.62;pts.forEach(function(q,i){var inC=i<N*.18;
q.f1x=c1x+(inC?(r()-.5)*.14:(r()-.5)*.5+.05);
q.f1y=c1y+(inC?(r()-.5)*.12:(r()-.5)*.5-.1);
q.f2x=.66+(r()-.5)*.44;q.f2y=.38+(r()-.5)*.44;});
letters=[];for(i=0;i<3;i++)letters.push({t:r()*.7,x:.55+r()*.2,y:.45+r()*.2,d:.25+r()*.3});
}
function sync(){if(!cv)return;cw=cv.clientWidth;ch=cv.clientHeight;if(!cw||!ch)return;
var d=Math.min(dpr,W.devicePixelRatio||1);
if(cv.width!==Math.round(cw*d)||cv.height!==Math.round(ch*d)){cv.width=Math.round(cw*d);cv.height=Math.round(ch*d)}
if(ctx){ctx.setTransform(d,0,0,d,0,0)}var o=N;build();if(o!==N&&rm)render(tm)}
function pos(q,t){ // returns [x,y,stage]
var amb=Math.sin(t*.0003+q.o)*4+Math.cos(t*.0002+q.k*6.28)*3;
var ambY=Math.cos(t*.00025+q.k*6.28)*4;
var x,y,a1,a2,pa=ease(Math.max(0,Math.min(1,(p-.3)/.4)));
var out1=ease(Math.max(0,Math.min(1,(p-.26)/.12))),in2=ease(Math.max(0,Math.min(1,(p-.58)/.12)));
if(p<.3){a1=1;a2=0}else if(p<.7){a1=1-out1;a2=0}else{a1=1-out1;a2=in2}
var fx=q.f1x*cw+amb,fy=q.f1y*ch+ambY;
var gx=q.f2x*cw+amb*1.4,fy2=q.f2y*ch+ambY*1.4;
// travel position
var tx=q.x*cw+amb*.6+pa*300*q.s,ty=q.y*ch+ambY*.6+pa*220*q.s;
var k=ease(pa);
x=fx+(tx-fx)*k;y=fy+(ty-fy)*k;
if(a2>0){x=x+(gx-x)*a2;y=y+(fy2-y)*a2}
return{x:x,y:y,a1:a1,a2:a2,amb:amb}
}
function draw(t){
tm=t;if(!ctx||!cw)return;ctx.clearRect(0,0,cw,ch);
var i,j,q,a,b,dx,dy,al,Q=[];
for(i=0;i<N;i++){Q.push(pos(pts[i],t))}
var f1=Math.max(0,1-Math.max(0,Math.min(1,(p-.24)/.3))); // fig1 presence
// hairlines stage1
if(f1>0){ctx.strokeStyle='rgba(243,238,228,'+(0.34*f1)+')';ctx.lineWidth=.6;
for(i=0;i<N;i++)for(j=i+1;j<N;j++){if((i*7+j)%3)continue;
dx=Q[i].x-Q[j].x;dy=Q[i].y-Q[j].y;if(dx*dx+dy*dy<1600)ln(Q[i].x,Q[i].y,Q[j].x,Q[j].y)}}
// particles
for(i=0;i<N;i++){q=Q[i];var o=Math.sin(t*.0005+pts[i].o)*.25+.75,s=q.s*1.15;
var acc=pts[i].k<.022&&f1>0.05;
ctx.fillStyle=acc?'rgba(196,115,26,'+(.85*f1)+')':'rgba(243,238,228,'+(.85*o)+')';
ctx.beginPath();ctx.arc(q.x,q.y,acc?1.6:s,0,6.28);ctx.fill()}
// parallel travel lines
if(p>.26&&p<.9){var tl=Math.sin(Math.min(1,(p-.26)/.64)*Math.PI);
ctx.strokeStyle='rgba(243,238,228,'+(0.17*tl)+')';ctx.lineWidth=.5;
for(i=0;i<8;i++){var y0=(i/8)*ch-30+Math.sin(t*.0003+i)*3;ln(0,y0,cw*.4,y0+cw*.22)}}
// sun: rises p .35→.95
var sp=ease(Math.max(0,Math.min(1,(p-.32)/.6)));
if(sp>0){var sx=cw*.16,sy=ch*(1.05-sp*.75)+Math.sin(t*.0003)*2;
ctx.save();ctx.shadowColor='rgba(196,115,26,'+(0.35*sp)+')';ctx.shadowBlur=Math.max(40,cw*.04);ctx.fillStyle='rgba(196,115,26,'+(0.3*sp)+')';ctx.beginPath();ctx.arc(sx,sy,10+sp*14,0,6.28);ctx.fill();ctx.restore();
ctx.strokeStyle='rgba(196,115,26,'+(0.14*sp)+')';ctx.lineWidth=.8;
ctx.beginPath();ctx.arc(sx,sy,26+sp*22,0,6.28);ctx.stroke();
// horizon haze
ctx.strokeStyle='rgba(243,238,228,'+(0.24*sp)+')';
for(i=0;i<4;i++)ln(cw*.15,sy+18+i*9+Math.sin(t*.0002+i)*2,cw*.85,sy+18+i*9)}
// ring pulse at arrival
if(p>.72){var rp=(p-.72)/.28,ph=(t*.001)%1,rr=20+ph*90,ra=(1-ph)*.45*Math.min(1,rp*2);
if(ra>0){var cxx=cw*.16,cyy=ch*.38;ctx.strokeStyle='rgba(243,238,228,'+ra+')';ctx.lineWidth=.7;
ctx.beginPath();ctx.arc(cxx,cyy,rr,0,6.28);ctx.stroke()}}
}
function render(t){draw(t)}
function loop(t){if(!running)return;draw(t);raf=rAF(loop)}
function vis(){if(!rm){document.hidden?API.pause():(auto&&API.resume())}}
return API={
init:function(c,o){o=o||{};cv=c;try{ctx=c.getContext('2d')}catch(e){ctx=null}if(!ctx)return;
seed=(o.seed||1)|0;dpr=o.dpr||1.5;rm=!!o.reducedMotion;auto=o.autoplay!==false;p=0;
sync();
if(cObs){ro=new cObs(sync);ro.observe(c)}else{W.addEventListener('resize',sync)}
document.addEventListener('visibilitychange',vis);
if(rm){draw(0)}else if(auto){running=true;raf=rAF(loop)}
},
setProgress:function(v){p=Math.max(0,Math.min(1,v||0));if(rm)draw(tm||0)},
render:render,
pause:function(){running=false;if(raf){W.cancelAnimationFrame(raf);raf=0}},
resume:function(){if(rm||running)return;running=true;raf=rAF(loop)},
destroy:function(){API.pause();if(ro)ro.disconnect();W.removeEventListener('resize',sync);
document.removeEventListener('visibilitychange',vis);ctx=null;cv=null}
}};
window.JeevanaBackdrop=API();})();
