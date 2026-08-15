// v85 — 결과 2쪽 분할·용어 쉬움·지난 대화·퀘스트 토글
const fs=require("fs"), {JSDOM}=require("jsdom");
const html=fs.readFileSync("i.html","utf8");
// 지원 언어 수는 늘어난다 — 숫자를 박아 두지 말고 언어 고르기 단추에서 센다
const LANGS=(html.match(/data-lang="[a-z]+"/g)||[]).length;
const py=fs.readFileSync("/sessions/gifted-youthful-edison/mnt/음성 대화형 챗봇/main.py","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};
const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://korean-dic.onrender.com/",pretendToBeVisual:true,
 beforeParse(w){w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
  w.HTMLMediaElement.prototype.play=()=>Promise.resolve(); w.HTMLMediaElement.prototype.pause=()=>{};
  try{w.localStorage.setItem("uiLang","ko");w.localStorage.setItem("userName","남정");w.localStorage.setItem("entryDoneCount","3");w.sessionStorage.setItem("splashSeen","1");}catch(e){}}});
const w=dom.window, d=w.document;
setTimeout(()=>{
  console.log("── 결과 두 장 ──");
  // v88 — 결과는 네 장: ⓪ 자기 성찰 ① 대화 흐름 ② 상호작용 대화 능력 ③ 총평
  ok("네 장이 다 있다", [0,1,2,3].every(i => !!d.getElementById("resPage" + i)));
  ok("⓪ 스스로 매기는 별 다섯", d.querySelectorAll("#resPage0 .self-star").length === 5);
  ok("① 점수·발화·시간", !!d.querySelector("#resPage1 #rcScoreVal") && !!d.querySelector("#resPage1 #rcTimeVal"));
  ok("① 기능 단계·유형", !!d.querySelector("#resPage1 #rpResultStages") && !!d.querySelector("#resPage1 #rpAbcRow"));
  ok("② 상호작용 대화 능력", !!d.querySelector("#resPage2 #rpIdcList"));
  ok("③ 총평은 줄글", !!d.querySelector("#resPage3 #rpReviewEl"));
  ok("쪽 표시 점 4개", d.querySelectorAll("#rpResultOverlay .res-dot").length === 4);
  ok("자유 대화는 세 장", d.querySelectorAll("#freeDots .res-dot").length === 3
     && [0,1,2].every(i => !!d.getElementById("freePage" + i)));
  ok("이전·다음이 한 줄 두 칸", /\.res-actions \{[^}]*grid-template-columns: 1fr 1fr/.test(html));
  ok("쪽 문구 지원 언어 전부에", (html.match(/resNext:"/g)||[]).length===LANGS);
  console.log("── 용어 쉬움 ──");
  ok("어려운 말 금지 지시", /다음 말은 절대 쓰지 마라/.test(py) && /화행, 레지스터, 담화/.test(py));
  ok("'~해 보세요' 로 쓰라고 지시", /'~하지 못했습니다'보다 '~해 보세요'/.test(py));
  ok("'화계' 표기가 사라졌다", !/화계/.test(html) && !/화계/.test(py));
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
