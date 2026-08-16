/* v96 — 총평이 곧바로 흘러나오는가 (스트리밍 · 소켓 유지) */
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync(process.argv[3] || "main.py", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

console.log("── 서버: 언제 시작하나 ──");
ok("종료 신호를 받자마자 총평부터 띄운다",
   /review_task = asyncio\.create_task\(_review_job\(\)\)[\s\S]{0,300}?for _ in range\(40\)/.test(py));
ok("분석·프로파일을 기다리지 않는다", !/await run_idc_profile\(\)[\s\S]{0,200}?run_review/.test(py));
ok("옛 경로(_send_review_later)는 없앴다", !/_send_review_later/.test(py));

console.log("── 서버: 어떻게 보내나 ──");
ok("한꺼번에 말고 흘려보낸다", /generate_content_stream/.test(py) && /async for chunk in stream/.test(py));
ok("조각마다 review_chunk", /"type": "review_chunk", "text": text/.test(py));
ok("끝나면 review_done", /"type": "review_done", "text": text/.test(py));
ok("학습자가 닫으면 생성을 멈춘다", /return ""\s*#\s*학습자 쪽이 이미 닫혔다/.test(py));
// v101 — 숫자를 박아 두지 않는다. 총평 입력이 프로파일(80턴)보다 짧기만 하면 된다.
const _n = (py.match(/총평은 흐름만 보면 되므로 (\d+)턴/)||[])[1];
ok("총평 입력을 프로파일보다 짧게", !!_n && Number(_n) <= 40 && py.includes("convo[-"+_n+":]"));

console.log("── 클라이언트: 소켓을 살려 두는가 ★ ──");
ok("총평 기다리는 중이면 소켓을 안 닫는다",
   /if \(reviewPending\) \{[\s\S]{0,400}?reviewWs = ws;/.test(html));
ok("종료를 누를 때 기다림을 켠다", (html.match(/reviewPending = true;/g) || []).length === 2);
ok("다 받으면 정리한다", /closeReviewWs\(\);\s*\/\/ 다 받았으니/.test(html));
ok("안 오면 30초 뒤 정리", /setTimeout\(closeReviewWs, 30000\)/.test(html));
ok("홈으로 나가도 정리", /function goHome\(\) \{\s*\n\s*try \{ closeReviewWs\(\); \}/.test(html));

console.log("── 클라이언트: 화면 ──");
ok("조각을 이어 붙인다", /msg\.type === "review_chunk"/.test(html)
   && /reviewBuf \+= \(msg\.text \|\| ""\)/.test(html));
// ★ v103에서 겪은 사고 — 총평이 점수(rpFinal)보다 먼저 도착하는데
//   `if (rpFinal)` 로 받고 있어서 통째로 버려졌다. 다시는 그러지 않게 못 박는다.
ok("★ 총평을 점수와 무관하게 담아 둔다", /let reviewBuf = ""/.test(html));
ok("★ rpFinal 이 없어도 조각을 버리지 않는다",
   !/if \(rpFinal\) rpFinal\.review = \(rpFinal\.review \|\| ""\) \+/.test(html));
ok("★ 결과 화면이 담아 둔 총평을 먼저 본다", /reviewBuf \|\| \(rpFinal && rpFinal\.review\)/.test(html)
   && /reviewBuf \|\| rpFinal\.review/.test(html));
ok("★ 새 대화가 시작되면 비운다", /reviewBuf = "";\s*\/\/ 지난 대화의/.test(html));
ok("두 화면 모두 채운다", (html.match(/\["rpReviewEl", "freeReviewEl"\]/g) || []).length >= 2);
ok("쓰는 중엔 붓끝이 깜빡인다", /\.rev-body\.writing::after/.test(html));
ok("다 쓰면 커서를 지운다", /el\.classList\.remove\("writing"\)/.test(html));
ok("다 받은 뒤에 기록에 얹는다", /review_done[\s\S]{0,1200}?buildTranscriptText\(\)/.test(html));

console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail ? 1 : 0);
