const fs=require('fs');const {JSDOM,VirtualConsole}=require('jsdom');
const SRC="app.html";
const vc=new VirtualConsole();let err=0;vc.on('jsdomError',e=>{err++;console.log('  ✗',String(e).slice(0,180));});
const dom=new JSDOM(fs.readFileSync(SRC,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/',virtualConsole:vc,
 beforeParse(w){w.fetch=()=>Promise.resolve({ok:false,status:0,json:()=>Promise.resolve({})});
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.play=()=>Promise.resolve();w.HTMLMediaElement.prototype.pause=()=>{};w.HTMLMediaElement.prototype.load=()=>{};
  w.AudioContext=w.webkitAudioContext=function(){const g={gain:{value:0,cancelScheduledValues(){},setValueAtTime(){},linearRampToValueAtTime(){}},connect:x=>x,disconnect(){}};
    return {state:'running',currentTime:0,destination:{},createGain:()=>g,createMediaElementSource:()=>g,createMediaStreamSource:()=>g,createAnalyser:()=>Object.assign({},g,{fftSize:512,getFloatTimeDomainData(){}}),resume:()=>Promise.resolve(),close:()=>Promise.resolve()};};
 }});
const w=dom.window;
let bad=0; const ok=(m,c,x)=>{console.log((c?"  ✅ ":"  ❌ ")+m+(c?"":"   "+(x===undefined?"":x)));if(!c)bad++;};
setTimeout(()=>{
  if(err){console.log("💥 화면이 죽었다");process.exit(1);}
  const qs = w.eval('questToday("rp")');
  ok("오늘의 퀘스트가 세 개 뽑힌다", qs.length===3, qs.length);
  ok("어려움 값(lv)은 안쪽에 그대로 있다", qs.map(q=>q.lv).join(",")==="0,1,2", qs.map(q=>q.lv).join(","));
  // 퀘스트 카드 그려 보기
  // 퀘스트 카드를 실제로 그려 본다
  const box = w.document.createElement("div");
  w.document.body.appendChild(box);
  w.eval('window.__qbox = document.body.lastElementChild;');
  w.eval('questRender(window.__qbox, "rp", false)');
  const cardTxt = box.textContent;
  console.log("\n  ── 퀘스트 카드 ──");
  box.querySelectorAll(".qz-row").forEach(r => console.log("     " + r.textContent.trim()));
  const peek = w.eval('(function(){let s="";const d=qzDoneToday();questToday("rp").forEach(q=>{s+=(d.has(q.id)?"✓ ":"☐ ")+questLabel(q.id)+"\\n";});return s})()');
  console.log("\n  ── 호아랑이 알려 주는 목록 ──");
  peek.trim().split("\n").forEach(l=>console.log("     "+l));
  ok("카드에 ★ 이 없다", cardTxt.indexOf("★")<0, cardTxt.slice(0,60));
  ok("카드에 qz-lv 칸이 아예 없다", box.querySelectorAll(".qz-lv").length===0);
  ok("알림 목록에 ★ 이 없다", peek.indexOf("★")<0, peek);
  const src=fs.readFileSync(SRC,'utf8');
  // 퀘스트 쪽 별만 없어야 한다 — 자가 별점(selfRating)은 그대로 둔다
  const qzStars = (src.match(/"★"\.repeat\(q\.lv\)/g)||[]).length;
  ok("퀘스트 쪽 ★ 이 하나도 안 남았다", qzStars===0, qzStars+"군데");
  const selfStars = (src.match(/"★"\.repeat\(selfRating\)/g)||[]).length;
  ok("자가 별점의 ★ 은 살아 있다", selfStars===1, selfStars+"군데");
  console.log(bad?`\n💥 ${bad}건`:"\n🎉 퀘스트에서 별이 빠졌다");
  process.exit(bad?1:0);
},1200);
