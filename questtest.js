// 오늘의 퀘스트 — 집계·추첨·표시 검사
const fs=require("fs"), {JSDOM}=require("jsdom");
const html=fs.readFileSync("i.html","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};
const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://korean-dic.onrender.com/",pretendToBeVisual:true,
 beforeParse(w){w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
  w.HTMLMediaElement.prototype.play=()=>Promise.resolve(); w.HTMLMediaElement.prototype.pause=()=>{};
  try{w.localStorage.setItem("uiLang","ko");w.localStorage.setItem("userName","남정");w.localStorage.setItem("entryDoneCount","3");w.sessionStorage.setItem("splashSeen","1");}catch(e){}}});
const w=dom.window,d=w.document;
setTimeout(()=>{
  console.log("── 표시 ──");
  const btn=d.getElementById("qzBtn");
  ok("홈에 작은 호아랑 버튼이 있다", !!btn);
  ok("홈에 큰 카드는 없다", !d.getElementById("qzHome"));
  // 버튼을 누르면 호아랑이 빼꼼 나와 퀘스트를 읽어 준다
  btn.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));
  const peek=d.getElementById("hamPeek"), ptx=d.getElementById("hamPeekText");
  ok("호아랑이 빼꼼 나온다", peek && peek.classList.contains("show"));
  const items=ptx.querySelector(".qz-items");
  const lines=((items&&items.textContent)||"").split("\n").filter(x=>/^[✓☐]/.test(x.trim()));
  ok(`말풍선에 퀘스트 3개 (${lines.length}개)`, lines.length===3);
  ok("난이도 표시가 섞여 있다", /★/.test(ptx.textContent));
  ok("제목은 굵게 · 항목은 얇게(같은 크기)", !!items && /\.hp-bubble \.qz-items \{[^}]*font-weight: 400/.test(html));
  ok("본 뒤에는 빨간 점이 사라진다", btn.classList.contains("seen"));
  console.log("   →", lines.map(x=>x.replace(/^[✓☐]/,"").trim()).join(" / "));

  console.log("\n── 같은 날은 같은 퀘스트 ──");
  ok("날짜 시드라 새로고침해도 안 바뀐다", /const seed = d\.getFullYear\(\) \* 10000/.test(html));

  console.log("\n── 비언어적 행위는 제외 ──");
  ok("비언어 관련 퀘스트 없음", !/시선|표정|고개|제스처/.test(html.match(/const QUEST_DEFS = \[[\s\S]*?\];/)[0]));

  console.log("\n── IDC 요소 연결 ──");
  const defs=html.match(/const QUEST_DEFS = \[[\s\S]*?\];/)[0];
  ["기능 단계","화제 관리","차례 관리","의사소통 단절 수정","상호작용적 듣기","맥락·정체성 인식"].forEach(el=>{
    ok(`${el} 퀘스트 있음`, defs.includes(el));
  });

  console.log("\n── 서버(LLM) 판정 퀘스트 ──");
  const defs2=html.match(/const QUEST_DEFS = \[[\s\S]*?\];/)[0];
  ["qRefuse","qCond","qCircum","qReturn","qAlt","qHold","qSelfFix","qNewTopic"].forEach(id=>{
    ok(`${id} 정의됨`, defs2.includes(id));
  });
  ok("LLM 퀘스트는 주제 대화 전용", (defs2.match(/llm:1, chk/g)||[]).length===8 && !/llm:1[^\n]*mode:"free"/.test(defs2));
  ok("서버가 보낸 quests 를 흡수한다", /\(msg\.quests \|\| \[\]\)\.forEach/.test(html));
  ok("문구가 12개 언어에 있다", (html.match(/qRefuse:"/g)||[]).length===12);

  console.log("\n── 결과를 자료로 남긴다 ──");
  ok("지난 대화 기록에 quests 저장", /title, preview, text, quests, stats/.test(html));
  ok("서버 업로드 정보에 quests 포함", /quests: \(function \(\) \{ try \{ return questResult/.test(html));
  ok("집계값(idcStats)도 함께", /idcStats:/.test(html));

  console.log("\n── 대화 중에는 감춘다 ──");
  ok("홈에서만 버튼이 보인다", /body\[data-screen="home"\] \.qz-btn \{ display: grid/.test(html));

  console.log("\n── 퀘스트를 깨면 ──");
  ok("대화가 끝나면 조용히 기록만", /function questFinish\(mode\)/.test(html));
  ok("도장은 끝난 뒤 조용히 찍힌다", /try \{ questFinish\("rp"\); \} catch/.test(html));
  // v85 — 저자 요청으로 메달 줄을 뺐다. 달성 여부는 ✓/☐ 목록으로만 보인다.
  ok("메달 줄은 없다(✓/☐로만)", !/items \+= "\\n🏅 " \+ got\.length/.test(html));

  console.log("\n── IDC 도장판 ──");
  ok("도장판 8칸(비언어 제외)", /const IDC_BOARD = \["stage", "topic", "move", "turn", "repair", "strategy", "listen", "context"\]/.test(html));
  ok("깬 요소에 도장이 찍힌다", /stampsAdd\(earned\)/.test(html));
  ok("기기에 누적 저장", /localStorage\.setItem\(STAMP_KEY/.test(html));
  ok("결과 화면에 도장판도 없다(홈에서만)", !d.getElementById("stFree") && !d.getElementById("stRp"));
  ok("결과 화면에는 퀘스트 목록이 없다", !d.getElementById("qzFree") && !d.getElementById("qzRp"));
  ok("홈·결과가 같은 목록(mode 고정)", /function questToday\(mode\) \{[\s\S]{0,240}mode = "rp";/.test(html));
  ok("오늘 깬 것을 하루 단위로 모은다", /function qzDoneToday\(\)/.test(html) && /localStorage\.setItem\(qzDoneKey\(\)/.test(html));
  ok("빼꼼에 체크 표시", /done\.has\(q\.id\)/.test(html));
  ok("비언어 안내가 사라졌다", !/idcNoteEl/.test(html));
  ok("칸 이름이 12개 언어", (html.match(/st_stage:"/g)||[]).length===12);
  ok("퀘스트마다 요소 키(ek)가 붙어 있다", (html.match(/ek:"/g)||[]).length>=21);

  console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
  process.exit(fail?1:0);
},900);
