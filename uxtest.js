// v85 — 결과 2쪽 분할·용어 쉬움·지난 대화·퀘스트 토글
const fs=require("fs"), {JSDOM}=require("jsdom");
const html=fs.readFileSync("app.html","utf8");
// 지원 언어 수는 늘어난다 — 숫자를 박아 두지 말고 언어 고르기 단추에서 센다
const LANGS=(html.match(/data-lang="[a-z]+"/g)||[]).length;
const py=fs.readFileSync("main.py","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};
const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://korean-dic.onrender.com/",pretendToBeVisual:true,
 beforeParse(w){w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
  w.HTMLMediaElement.prototype.play=()=>Promise.resolve(); w.HTMLMediaElement.prototype.pause=()=>{};
  try{w.localStorage.setItem("uiLang","ko");w.localStorage.setItem("userName","남정");w.localStorage.setItem("entryDoneCount","3");w.sessionStorage.setItem("splashSeen","1");}catch(e){}}});
const w=dom.window, d=w.document;
setTimeout(()=>{
  console.log("── 결과 두 장 ──");
  /* v141 — 결과는 여섯 장.
     ⓪ 자기 성찰(별점) ① 요소 자가 점검 ② 후기 ③ 대화 흐름 ④ 상호작용 대화 능력 ⑤ 총평
     ★ ①②가 ④보다 앞이어야 한다 — AI 판정을 보고 나서 자기를 매기면 자기 평가가 오염된다. */
  ok("여섯 장이 다 있다", [0,1,2,3,4,5].every(i => !!d.getElementById("resPage" + i)));
  ok("⓪ 스스로 매기는 별 다섯", d.querySelectorAll("#resPage0 .self-star").length === 5);
  ok("③ 점수·발화·시간", !!d.querySelector("#resPage3 #rcScoreVal") && !!d.querySelector("#resPage3 #rcTimeVal"));
  ok("③ 기능 단계·유형", !!d.querySelector("#resPage3 #rpResultStages") && !!d.querySelector("#resPage3 #rpAbcRow"));
  ok("④ 상호작용 대화 능력", !!d.querySelector("#resPage4 #rpIdcList"));
  ok("① 요소 자가 점검이 AI 판정보다 앞", !!d.querySelector("#resPage1 #selfChkList"));
  ok("② 후기", !!d.querySelector("#resPage2 #selfNoteEl"));
  ok("⑤ 총평은 줄글", !!d.querySelector("#resPage5 #rpReviewEl"));
  ok("쪽 표시 점 6개", d.querySelectorAll("#rpResultOverlay .res-dot").length === 6);
  ok("자유 대화는 다섯 장", d.querySelectorAll("#freeDots .res-dot").length === 5
     && [0,1,2,3,4].every(i => !!d.getElementById("freePage" + i)));
  ok("이전·다음이 한 줄 두 칸", /\.res-actions \{[^}]*grid-template-columns: 1fr 1fr/.test(html));
  ok("쪽 문구 지원 언어 전부에", (html.match(/resNext:"/g)||[]).length===LANGS);
  console.log("── 용어 쉬움 ──");
  ok("어려운 말 금지 지시", /다음 말은 절대 쓰지 마라/.test(py) && /화행, 레지스터, 담화/.test(py));
  ok("'~해 보세요' 로 쓰라고 지시", /'~하지 못했습니다'보다 '~해 보세요'/.test(py));
  /* ★ v119 — 이 검사는 「학습자가 어려운 학술어를 보지 않게 한다」는 뜻이었다.
     그런데 파일 전체를 훑는 바람에, **모델에게 주는 프롬프트와 주석**까지 걸렸다.
     모델에게는 「화계」가 정확한 말이라 오히려 써야 한다 — 두루뭉술하게 쓰면
     해요체와 합쇼체를 구별하지 못한다(v118의 원인이 바로 그것이었다).
     그래서 학습자가 보는 곳(화면 문구)만 엄히 보고,
     서버에는 「총평에 그 말을 쓰지 마라」는 금지가 있는지를 본다. */
  /* ★ v120 — 주석까지 훑는 바람에 「이 코드가 화계를 어떻게 다루는지」를
     적어 둔 설명글이 걸렸다. 주석은 학습자가 보지 않는다. 떼고 본다. */
  const shown = html.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  ok("'화계' 가 화면 문구에 없다", !/화계/.test(shown));
  ok("총평이 어려운 학술어를 금지한다", /화계, 합쇼체, 해요체, 해체/.test(py));
  console.log("── 자유 수다 ──");
  ok("말풍선 이모지 제거", !/freeFbTitle:"💬/.test(html));
  ok("'곧 추가될 예정' 줄 제거", !d.getElementById("freeFbBodyEl"));
  console.log("── 지난 대화 ──");
  // v87 — 저자 요청으로 3개 제한을 풀었다. 저장된 대화(최대 30개)를 모두 보이고,
  //        항목을 눌러 그 자리에서 펼치고 다시 눌러 접는다.
  ok("목록은 전부 보인다", /list\.forEach\(\(it, i\)/.test(html) && !/list\.slice\(0, 3\)/.test(html));
  ok("항목 안에서 펼친다", /class="hi-body"/.test(html) && /\.hist-item\.open \.hi-body/.test(html));
  ok("다시 누르면 접힌다", /function toggleHistItem/.test(html) && /if \(wasOpen\)/.test(html));
  // 목록은 다시 길게(52vh), 펼친 기록은 그 안에서 34vh — 내보내기·닫기 버튼이 밀리지 않는 선
  ok("목록·펼침 높이", /\.hist-list \{[^}]*max-height: calc\(52vh/.test(html) && /\.hi-body \{[^}]*max-height: calc\(34vh/.test(html));
  console.log("── 퀘스트 ──");
  ok("다시 누르면 닫힌다", /if \(el && el\.classList\.contains\("show"\) && el\.classList\.contains\("qz"\)\) \{ hamPeekHide\(\); return; \}/.test(html));
  ok("메달 요약 제거", !/🏅 " \+ got\.length/.test(html));
  console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
  process.exit(fail?1:0);
},900);
