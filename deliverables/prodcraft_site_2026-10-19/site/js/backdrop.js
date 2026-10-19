window.ProdCraftBackdrop=(function(){"use strict";
function mul(s){return function(){s|=0;s=s+0x6D2B79F5|0;var t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
var AC="#c8a35c",WH="#f7f3ec";
function cl(v){return v<0?0:v>1?1:v}
function es(v){v=cl(v);return v*v*(3-2*v)}
function mx(a,b,t){return a+(b-a)*t}
var M=null;
function make(cv,o){
 var seed=(o&&o.seed)||1,dpr=(o&&o.dpr)||1.5,rm=!!(o&&o.reducedMotion),ap=!o||o.autoplay!==false;
 var ctx=cv&&cv.getContext?cv.getContext("2d"):null,ro=null,raf=0,run=ap,pr=0,n=0,W=0,H=0,co=1;
 var ax,ay,gx,gy,ln,dl,sp,ph,al,sz,kx=0,ky=0;
 function gen(){
  W=cv.clientWidth||300;H=cv.clientHeight||150;
  n=Math.round(W*H/9000);n=Math.max(90,Math.min(260,n||90));
  var r=mul((seed*97+n)|0),i;
  var hx=[0.28+0.08*r(),0.6+0.12*r(),0.42+0.16*r()],hy=[0.3+0.1*r(),0.48+0.14*r(),0.66+0.1*r()];
  kx=hx[0];ky=hy[0];
  co=Math.max(1,Math.round(Math.sqrt(n*W/H)));var rw=Math.ceil(n/co);
  ax=[];ay=[];gx=[];gy=[];ln=[];dl=[];sp=[];ph=[];al=[];sz=[];
  for(i=0;i<n;i++){
   if(i%3){var h=(r()*2.99)|0;ax[i]=hx[h]+(r()-.5)*0.17;ay[i]=hy[h]+(r()-.5)*0.21;
    if(h===0){ax[i]=hx[0]+(r()-.5)*0.07;ay[i]=hy[0]+(r()-.5)*0.07}}
   else{ax[i]=r();ay[i]=r()}
   var c=i%co,w2=(i/co)|0;
   gx[i]=0.5+((c-(co-1)/2)/co)*0.74;gy[i]=0.5+((w2-(rw-1)/2)/rw)*0.74;
   ln[i]=r();dl[i]=r()*0.45;sp[i]=0.75+r()*0.5;ph[i]=r()*6.283;al[i]=0.45+r()*0.5;sz[i]=0.7+r()*1.1;
  }
 }
 function fit(){
  if(!ctx)return;
  W=cv.clientWidth||300;H=cv.clientHeight||150;
  var d=Math.min(dpr,window.devicePixelRatio||1);
  cv.width=Math.max(1,Math.round(W*d));cv.height=Math.max(1,Math.round(H*d));
  ctx.setTransform(d,0,0,d,0,0);gen();if(rm)draw(0);
 }
 function draw(t){
  if(!ctx)return;
  ctx.clearRect(0,0,W,H);
  var p=pr,f1=es((p-0.28)/0.12),f2=es((p-0.62)/0.12),jp=cl((p-0.3)/0.4);
  var tm=rm?0:t,i,j,X,Y;
  var px=[],py=[];
  for(i=0;i<n;i++){
   var dx=Math.sin(tm*3e-4+ph[i])*2.2,dy=Math.cos(tm*2.6e-4+ph[i]*1.7)*2.2;
   var aX=ax[i]*W+dx,aY=ay[i]*H+dy;
   var u=cl((jp-dl[i])/(1-dl[i]))*sp[i];
   var bX=(u*1.3-0.15)*W,bY=(0.1+(u*1.3-0.15)*0.55+(ln[i]-0.5)*0.3)*H;
   X=mx(mx(aX,bX,f1),gx[i]*W+dx,f2);Y=mx(mx(aY,bY,f1),gy[i]*H+dy,f2);
   px[i]=X;py[i]=Y;
  }
  var hA=0.16*(1-f1);
  if(hA>0.003){ // near-neighbour hairlines of the first figure
   ctx.strokeStyle=WH;ctx.lineWidth=0.5;ctx.globalAlpha=hA;ctx.beginPath();
   for(i=0;i<n;i++)for(j=i+1;j<n;j++){var ddx=px[i]-px[j],ddy=py[i]-py[j],d2=ddx*ddx+ddy*ddy;
    if(d2<1600){ctx.moveTo(px[i],py[i]);ctx.lineTo(px[j],py[j])}}
   ctx.stroke();
  }
  var gA=0.13*f2;
  if(gA>0.003){ // calm grid hairlines
   ctx.strokeStyle=WH;ctx.lineWidth=0.5;ctx.globalAlpha=gA;ctx.beginPath();
   for(i=0;i<n-1;i++)if(i%co!==co-1){ctx.moveTo(px[i],py[i]);ctx.lineTo(px[i+1],py[i+1])}
   ctx.stroke();
  }
  var jA=0.09*f1*(1-f2);
  if(jA>0.003){ // faint parallel journey lines
   ctx.strokeStyle=WH;ctx.lineWidth=0.5;ctx.globalAlpha=jA;ctx.beginPath();
   for(i=0;i<8;i++){var o0=(i/7-0.5)*0.3;ctx.moveTo(-0.05*W,(0.1+o0)*H);ctx.lineTo(1.05*W,(0.1+1.05*0.55+o0)*H)}
   ctx.stroke();
  }
  for(i=0;i<n;i++){ // particles
   ctx.globalAlpha=al[i];ctx.fillStyle=(i%53===0)?AC:WH;
   ctx.beginPath();ctx.arc(px[i],py[i],sz[i],0,6.2832);ctx.fill();
  }
  if(f1<1){ // subject cluster mark
   ctx.globalAlpha=0.85*(1-f1);ctx.fillStyle=AC;
   ctx.beginPath();ctx.arc(kx*W,ky*H,2.4,0,6.2832);ctx.fill();
  }
  var bA=f1*(1-f2); // serif initials dissolving along the journey
  for(i=0;i<3;i++){
   var e=cl((jp-0.08-i*0.2)/0.32),a=0.22*Math.sin(Math.PI*e)*bA;
   if(a>0.004){
    var lx=(0.3+i*0.2)*W,ly=(0.12+(0.3+i*0.2)*0.55)*H;
    ctx.globalAlpha=a;ctx.fillStyle=WH;
    ctx.font="600 "+(11+i*2)+"px Georgia,'Times New Roman',serif";
    ctx.fillText("P",lx,ly);
    ctx.globalAlpha=a*0.6;
    for(j=0;j<3;j++){ctx.beginPath();ctx.arc(lx+9+j*4,ly+2+j*3,0.9,0,6.2832);ctx.fill()}
   }
  }
  var rp=es((p-0.76)/0.2); // single pulse around the settled cluster
  if(rp>0&&rp<1){
   ctx.globalAlpha=0.3*(1-rp);ctx.strokeStyle=AC;ctx.lineWidth=1;
   ctx.beginPath();ctx.arc(kx*W,ky*H,rp*Math.min(W,H)*0.33,0,6.2832);ctx.stroke();
  }
  ctx.globalAlpha=1;
 }
 function loop(ts){raf=0;if(!run||rm||document.hidden)return;draw(ts);raf=requestAnimationFrame(loop)}
 function start(){if(!ctx)return;if(rm){draw(0);return}if(!raf&&!document.hidden)raf=requestAnimationFrame(loop)}
 function vis(){if(document.hidden){if(raf){cancelAnimationFrame(raf);raf=0}}else if(run)start()}
 function no(){}
 if(!ctx)return{set:no,draw:no,pause:no,resume:no,destroy:no};
 fit();
 if(window.ResizeObserver){ro=new ResizeObserver(fit);ro.observe(cv)}
 else window.addEventListener("resize",fit);
 document.addEventListener("visibilitychange",vis);
 if(ap)start();
 return{
  set:function(p){pr=cl(p);if(rm)draw(0)},
  draw:draw,
  pause:function(){run=false;if(raf){cancelAnimationFrame(raf);raf=0}},
  resume:function(){run=true;start()},
  destroy:function(){run=false;if(raf){cancelAnimationFrame(raf);raf=0}
   if(ro)ro.disconnect();window.removeEventListener("resize",fit);
   document.removeEventListener("visibilitychange",vis)}
 };
}
return{
 init:function(c,o){if(M)M.destroy();M=make(c,o||{})},
 setProgress:function(p){if(M)M.set(p)},
 render:function(t){if(M)M.draw(t)},
 pause:function(){if(M)M.pause()},
 resume:function(){if(M)M.resume()},
 destroy:function(){if(M){M.destroy();M=null}}
};
})();
