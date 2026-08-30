// v84 — IDC 강화 전수 검사
const fs=require("fs");
const html=fs.readFileSync("app.html","utf8");
// 지원 언어 수는 늘어난다 — 숫자를 박아 두지 말고 언어 고르기 단추에서 센다
const LANGS=(html.match(/data-lang="[a-z]+"/g)||[]).length;
const py=fs.readFileSync("main.py","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};
console.log("── ⓐ 자유 수다에도 IDC ──");
// v152 — 인자 목록을 글자로 대조하다 past_mem 이 늘면서 깨졌다.
// 「자유 대화 갈래에서 두 블록이 이어 붙는가」만 본다.
ok("자유 수다 프롬프트에 MKO 블록",
   /system_prompt = build_system_prompt\([^)]*\)\s*\\\s*\n\s*\+ build_mko_block/.test(py));
ok("비계 주입이 자유 대화 허용", /if sess is None:\s*#\s*자유 대화에도 비계 갱신/.test(py));
ok("분석이 자유 수다 허용", /stages_txt = "\(자유 대화 — 기능단계 없음/.test(py));
ok("프로파일이 자유 수다 허용", !/if rp_plan is None or not convo:\s*\n\s*return blank/.test(py));
ok("최종 분석 두 모드 공통", /await run_analysis\(final=True\)\s+#\s*자유 대화도/.test(py));
ok("자유 수다 결과에 IDC 자리", /id="freeIdcList"/.test(html));
ok("자유 수다가 final_score 를 기다린다", /function endFreeSession\(\)[\s\S]{0,400}end_session/.test(html));
console.log("── ⓑ A/B/C 유형 ──");
ok("판정 요청(4) abc", /"A" 단순형/.test(py) && /"C" 확장형/.test(py));
ok("서버가 abc 저장", /rp_progress\["abc"\] = data\["abc"\]/.test(py));
ok("최종 페이로드에 abc", /"abc": rp_progress\["abc"\]/.test(py));
ok("결과 화면에 유형 배지", /id="rpAbcBadge"/.test(html) && /abcC:"확장형/.test(html));
ok("배지 문구 지원 언어 전부에", (html.match(/abcC:"/g)||[]).length===LANGS);
console.log("── ⓒ 대화이동 연쇄 ──");
ok("판정 요청(5) chains", /시작\(먼저 화제·요청을 엶\)/.test(py));
ok("연쇄 누적 저장", /rp_progress\["chains"\]\[k\] = max/.test(py));
ok("기록·업로드에 chains", /chains: \(rpFinal && rpFinal\.chains\)/.test(html));
console.log("── ⓓ 세션 너머 페이딩 ──");
ok("기기 누적을 URL 로 보낸다", /localStorage\.getItem\("idcCounts"\)/.test(html) && /"\/ws\/live\?idc="/.test(html));
ok("서버가 누적으로 시작", /prev_counts\.get\(k, 0\) for k in IDC_SCORED_KEYS/.test(py));
ok("수준을 누적에서 계산", /def _level_from/.test(py));
ok("끝나면 기기에 저장", /localStorage\.setItem\("idcCounts", JSON\.stringify\(msg\.idcCounts\)\)/.test(py+html));
console.log("── ②③① 미시 보강 ──");
ok("명료화 강제(변하지 않는 원칙)", /반드시 되물어라/.test(py));
ok("채움말 권하기", /'음…', '그러니까…'/.test(py));
ok("표현마다 idc 태그 요청", /idc — 이 표현이 주로 기르는 상호작용 요소/.test(py));
ok("연습 화면에 요소 배지", /id="prIdcBadge"/.test(html));
console.log("── TXT·홈 ──");
/* ★ v143 — CSS 한 줄을 **글자 그대로** 찾고 있었다. 그 줄이 없어지자 빨간불이 떴는데
   정작 단추는 멀쩡했다. 규칙이 어떻게 생겼느냐가 아니라 **죽었느냐**를 봐야 한다.
   (예전에는 .export-btn 을 통째로 죽이고 이것만 예외로 뚫었다.
    이제는 숨길 것을 아이디로 하나하나 적으므로 예외를 뚫을 일이 없다.) */
ok("지난 대화 TXT 살아 있다",
   !/#histExportBtn[^{]*\{[^}]*display:\s*none/.test(html)
   && /id="histExportBtn"/.test(html));
ok("홈 영상 줌 완화(좌우 안 자름)", /좌우를 자르지 않는다/.test(html) && !/object-position: 50% 18%/.test(html));
ok("카드·버튼 축소", /width: 46px; height: 46px;/.test(html) && /padding: 10px 18px; gap: 12px;/.test(html));
console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail?1:0);
