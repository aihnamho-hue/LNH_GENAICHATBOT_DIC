const fs=require("fs"), {JSDOM}=require("jsdom");
let FAIL=0;   // 재방문 사용자 경로에서 스크립트가 멈추는지 — vuBars·rpScriptOverlay 사고 유형
const html=fs.readFileSync("i.html","utf8");
function run(label, opts){
  const errs=[];
  const dom=new JSDOM(html,{runScripts:"dangerously",url:opts.url,pretendToBeVisual:true,
   beforeParse(w){
     w.matchMedia=(q)=>({matches:/standalone/.test(q)?!!opts.standalone:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
     w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
     w.HTMLMediaElement.prototype.play=()=>Promise.resolve(); w.HTMLMediaElement.prototype.pause=()=>{};
     try{ w.localStorage.setItem("uiLang","ko"); w.localStorage.setItem("userName","남정"); w.localStorage.setItem("entryDoneCount","3");
          w.sessionStorage.setItem("splashSeen","1"); }catch(e){}
     w.onerror=(m)=>errs.push(String(m));
   }});
  const w=dom.window,d=w.document;
  w.addEventListener("error",e=>errs.push(String(e.message)));
  return new Promise(r=>setTimeout(()=>{
    console.log(`\n══ ${label} ══`);
    if(errs.length){ FAIL++; console.log("  ❌ 로드 오류: "+errs.slice(0,2).join(" / ")); } else console.log("  ✅ 로드 오류 없음");
    console.log("  data-screen =", d.body.dataset.screen);
    const blockers=[];
    for(const sel of ["#splash","#installGate","#inappGate","#langOverlay","#kakaoBanner"]){
      const el=d.querySelector(sel); if(!el) continue;
      const hid=el.classList.contains("hidden")||el.hidden||el.style.display==="none";
      if(!hid) blockers.push(sel);
    }
    console.log(blockers.length? "  ★ 화면을 막는 것: "+blockers.join(", ") : "  ✅ 막는 것 없음");
    // 홈 카드가 실제로 눌리는지
    let hit=0; const c=d.getElementById("homeRpCard");
    if(c){ c.addEventListener("click",()=>hit++); c.dispatchEvent(new w.MouseEvent("click",{bubbles:true,cancelable:true})); }
    if(!hit) FAIL++;
    console.log(hit? "  ✅ 주제 대화 카드 눌림" : "  ❌ 주제 대화 카드 안 눌림");
    r();
  },1200));
}
(async()=>{
  await run("웹 브라우저(재방문)", {url:"https://korean-dic.onrender.com/"});
  await run("설치된 앱(standalone)", {url:"https://korean-dic.onrender.com/?src=app", standalone:true});
  await run("교사용 ?web=1", {url:"https://korean-dic.onrender.com/?web=1"});
  console.log(FAIL? `\n💥 실패 ${FAIL}건` : "\n🎉 재방문 경로 이상 없음");
  process.exit(FAIL?1:0);
})();
