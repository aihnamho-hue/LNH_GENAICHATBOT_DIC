// 인트로 영상을 누를 때, 그 클릭이 뒷화면 버튼까지 뚫고 가는지 확인
const fs=require("fs"), {JSDOM}=require("jsdom");
const SRC=process.argv[2]||require("path").join(__dirname,"templates","index.html");
const html=fs.readFileSync(SRC,"utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};

console.log("── 정적 확인 ──");
ok(".splash.gone 에 pointer-events:none 이 없다", !/\.splash\.gone \{[^}]*pointer-events:\s*none/.test(html));
ok("클릭 삼키기 함수 있음", /function swallowNextClick/.test(html));
ok("endSplash 가 삼키기를 호출", /sp\.classList\.add\("gone"\);\s*\n\s*swallowNextClick\(\)/.test(html));
ok("캡처 단계로 가로챈다", /addEventListener\("click", eat, true\)/.test(html));

console.log("\n── 실제 동작 ──");
const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://korean-dic.onrender.com/",pretendToBeVisual:true,
  beforeParse(w){
    w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
    w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
    w.HTMLMediaElement.prototype.play=()=>Promise.resolve();
    w.HTMLMediaElement.prototype.pause=()=>{};
  }});
const {window}=dom, d=window.document;
const sp=d.getElementById("splash");
ok("인트로가 떠 있다", !!sp && !sp.classList.contains("gone"));

// 뒷화면 카드가 눌리는지 감시
let pressed=[];
["homeRpCard","homeFreeCard"].forEach(id=>{
  const el=d.getElementById(id);
  if(el) el.addEventListener("click",()=>pressed.push(id));
});

// 인트로를 손가락으로 누른 상황을 재현: pointerdown → (오버레이 사라짐) → click 이 뒷화면에 도달
sp.dispatchEvent(new window.Event("pointerdown",{bubbles:true}));
ok("인트로가 닫혔다(.gone)", sp.classList.contains("gone"));

const card=d.getElementById("homeRpCard");
const ev=new window.MouseEvent("click",{bubbles:true,cancelable:true});
card.dispatchEvent(ev);
ok(`뒷화면 카드가 안 눌렸다 (눌린 것: ${pressed.length? pressed.join(","):"없음"})`, pressed.length===0);
ok("그 클릭이 취소됐다(preventDefault)", ev.defaultPrevented);

// 삼키기는 한 번만 — 다음 클릭은 정상 동작해야 한다
const ev2=new window.MouseEvent("click",{bubbles:true,cancelable:true});
card.dispatchEvent(ev2);
ok("다음 클릭은 정상 동작한다", pressed.length===1);

console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail?1:0);
