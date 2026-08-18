// 발화 연습 말차례 연쇄 — 학습자 선행 / 2항 / 3항
const fs=require("fs");
const html=fs.readFileSync("i.html","utf8");
// 지원 언어 수는 늘어난다 — 숫자를 박아 두지 말고 언어 고르기 단추에서 센다
const LANGS=(html.match(/data-lang="[a-z]+"/g)||[]).length;
const py=fs.readFileSync("/sessions/gifted-youthful-edison/mnt/음성 대화형 챗봇/main.py","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};
console.log("── 서버 ──");
ok("cue 빈 문자열 = 학습자 선행", /학습자가 먼저 말을 여는 자리면 빈 문자열로 둔다/.test(py));
ok("follow = 3항 연속체", /follow — text 바로 뒤에 올 상대의 반응/.test(py));
ok("질문–응답만 반복하지 말라고 지시", /질문–응답만 반복하지 마라/.test(py));
// 문구를 박아 두면 프롬프트를 다듬을 때마다 깨진다. 보장 장치가 있는지를 본다.
ok("여는 자리를 하나 이상 요구한다", /cue 빈 문자열을?\s*\*{0,2}하나 이상/.test(py) || /_balance_expr_positions/.test(py));
ok("★ 여는 자리가 없으면 서버가 만들어 준다", /def _balance_expr_positions/.test(py));
ok("★ 비어 있는 cue 를 도로 채우지 않는다", /if e\.get\("cue"\):\s*\n\s*e\["cue"\] =/.test(py));
ok("★ 자리 고르기가 대화문 붙이기보다 먼저", py.indexOf("_balance_expr_positions(stages)") < py.indexOf("_link_expr_to_script(stages, script)"));
ok("제안–거절–반응 예시", /제안–수락\/거절–반응/.test(py));
ok("정규화가 follow 를 받는다", /"follow": follow/.test(py));
ok("★ cue 필수 강제가 사라졌다", !/모든 표현에 반드시 채워라\. 빈 문자열 금지/.test(py));
console.log("\n── 화면 ──");
ok("exprFollow 있음", /function exprFollow/.test(html));
ok("cue 없으면 말풍선 숨김", /prCueRow\.classList\.toggle\("hidden", !isReply \|\| !cue\)/.test(html));
ok("선행 안내 문구로 갈아탄다", /t\(leadsOff \? "prStepLead" : "prStepReply"\)/.test(html));
ok("3항 말풍선 자리", /id="prFollowRow"/.test(html) && /id="prFollowText"/.test(html));
ok("선행 문구 지원 언어 전부에", (html.match(/prStepLead:"/g)||[]).length===LANGS);
ok("★ 말해 보기는 연속체 전체를 들려준다", /function prSeqPlay/.test(html) && /prPhase === "reply"\) prSeqPlay/.test(html));
ok("★ 음성이 끝나는 시점을 알려 준다", /return new Promise\(\(done\)/.test(html));
console.log("\n── 퀘스트 버튼 ──");
ok("창이 열리면 감춘다", /body\.ov-open \.qz-btn \{ display: none/.test(html));
ok("창 열림을 감지한다", /function syncOverlayFlag/.test(html) && /classList\.toggle\("ov-open", open\)/.test(html));
console.log("\n── 홈 영상 ──");
ok("폰에서 좌우를 자르지 않는다(줌 완화)", /좌우를 자르지 않는다/.test(html));
console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail?1:0);
