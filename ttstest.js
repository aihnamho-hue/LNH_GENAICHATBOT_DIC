/* v94 — 서버 음성이 한 번 실패해도 계속 쓰는가 · 총평 뒤따라 오기 */
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync(process.argv[3] || "main.py", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

console.log("── 발화 연습 음성 ──");
ok("한 번 실패했다고 영영 포기하지 않는다",
   !/geminiTtsDead\s*=\s*true;/.test(html) && !/if \(geminiTtsDead/.test(html));
ok("잠깐 쉬었다가 다시 시도한다", /TTS_COOLDOWN/.test(html) && /ttsColdUntil = Date\.now\(\) \+ TTS_COOLDOWN/.test(html));
ok("실패하면 한 번 더 해 본다", /for \(let i = 0; i < 2; i\+\+\)[\s\S]{0,400}?ttsFetch/.test(html));
ok("성공하면 쉼을 푼다", /ttsColdUntil = 0;/.test(html));
ok("미리 받아 두는 길도 같은 기준", /if \(!text \|\| ttsDown\(\)\) return;/.test(html));
ok("서버는 세 번 재시도 + 모델 교체", /for _ in range\(3\)/.test(py) && /_next_tts_model/.test(py));

console.log("── 총평은 결과 뒤에 따로 온다 ──");
ok("총평을 맨 먼저 시작한다", /review_task = asyncio\.create_task\(_review_job\(\)\)/.test(py));
ok("총평은 쓰이는 대로 흘려보낸다", /generate_content_stream/.test(py)
   && /"type": "review_chunk", "text": text/.test(py) && /"type": "review_done", "text": text/.test(py));
ok("클라이언트가 조각을 받는다", /msg\.type === "review_chunk"/.test(html) && /msg\.type === "review_done"/.test(html));
ok("받으면 두 화면 모두 채운다", /\["rpReviewEl", "freeReviewEl"\]/.test(html));
ok("다 받은 뒤 기록에 얹는다", /msg\.type === "review_done"[\s\S]{0,700}?buildTranscriptText\(\)/.test(html));
ok("기다리는 동안 '쓰는 중'을 보인다", /t\("revWait"\)/.test(html));
ok("'쓰는 중' 문구가 18개 언어", (html.match(/revWait:"/g) || []).length === 18);
ok("결과를 13초 안에 띄운다", /concludeRoleplay, 13000/.test(html) && /concludeFree, 13000/.test(html));

console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail ? 1 : 0);
