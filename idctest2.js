// ─────────────────────────────────────────────────────────────
// 「한국어 상호작용 대화 능력」 학습 화면 (v128)
//   ★ 하향식이 실제로 그렇게 도는가를 본다 — 순서가 뒤집히면 이 화면은 뜻이 없다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "templates/index.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let bad = 0;
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

console.log("── ① 하향식 순서 ──");
// 걸음은 넷이고, 뜻풀이는 **맨 뒤**여야 한다
const paint = /function idlPaint\(\)[\s\S]*?\n    \}/.exec(html)[0];
ok("걸음이 여섯이다 (v129: 형태·사용을 더함)", /for \(let i = 0; i < 6; i\+\+\)/.test(html));
ok("⓪ 들어가기가 첫 걸음", /if \(idl\.step === 0\)[\s\S]{0,400}idl-warm/.test(paint));
ok("① 듣기가 둘째", /if \(idl\.step === 1\)[\s\S]{0,300}idlScript\(false\)/.test(paint));
ok("② 추측이 셋째", /if \(idl\.step === 2\)[\s\S]{0,900}idl-opt/.test(paint));
ok("③ 의미가 넷째 — 설명은 맨 뒤다", paint.lastIndexOf("d.meaning") > paint.indexOf("idl-opt"));

console.log("── ② 표시는 추측이 끝난 뒤에만 ──");
// ①에서 불을 켜면 답을 주는 것이다. 이 검사가 이 화면의 핵심을 지킨다.
ok("① 듣기에서는 불을 안 켠다", /idlScript\(false\)/.test(paint) && !/step === 1[\s\S]{0,300}idlScript\(true\)/.test(paint));
ok("③ 의미에서 불을 켠다", /idlScript\(true\)/.test(paint));
ok("맞혀야 다음으로 넘어간다", /next\.disabled = \(idl\.picked !== q\.ans\)/.test(html));

console.log("── ③ 두 갈래 물음 ──");
/* ★ v129 — 두 갈래에서 세 갈래로. 둘이면 아무렇게나 눌러도 절반이 맞아
   「첫 시도에 맞혔는가」가 알아차림의 지표가 되지 못한다. */
ok("선택지가 셋이다", /wrong1/.test(py) && /wrong2/.test(py) && /"c"/.test(html));
ok("정답 자리를 섞는다", /cand\[i\], cand\[j\] = cand\[j\], cand\[i\]/.test(py));
ok("왜 셋인지 코드에 적어 두었다", /둘이면 아무렇게나 눌러도 절반이 맞는다/.test(py));
ok("오답도 그럴듯해야 한다고 못 박는다", /모르는 사람이 실제로 하는 오해/.test(py));
ok("틀려도 나무라지 않는다", /나무라지 말고/.test(py));
ok("틀리면 다시 고를 수 있다", /idl\.picked = ""; idlPaint\(\)/.test(html));

console.log("── ④ 이름 ──");
const KEYS = ["move", "topic", "turn", "repair", "strategy", "listen", "context"];
ok("일곱 요소", KEYS.every(k => new RegExp('key: "' + k + '"').test(html)));
/* ★ v131 — 방침이 바뀌었다. 아홉을 **모두 보이되** 둘은 「교실에서」로 표시한다.
   못 배우는 것을 아예 안 보이면 「없는 것」이 되어, 학습자가 상호작용 대화 능력의
   전체 모습을 알 수 없다. 여기서 배우는 것은 일곱이다. */
ok("아홉을 모두 보인다", /key: "stage"/.test(html) && /key: "nonverbal"/.test(html));
ok("배우는 것은 일곱", (html.match(/where: "here"/g) || []).length === 7,
   (html.match(/where: "here"/g) || []).length);
ok("교실에서 배우는 둘은 눌리지 않는다", /else b\.disabled = true;/.test(html));
const LESSON_BLOCK = (/^IDC_LESSON = \[[\s\S]*?^\]/m.exec(py) || [""])[0];
ok("서버 학습표는 일곱만", KEYS.every(k => LESSON_BLOCK.indexOf('"key": "' + k + '"') >= 0)
   && LESSON_BLOCK.indexOf('"key": "stage"') < 0 && LESSON_BLOCK.indexOf('"key": "nonverbal"') < 0);
ok("쉬운 이름이 크고 학술어는 작다",
   /\.idc-c1 \{[^}]*font-size: 15\.5px/.test(html) && /\.idc-c2 \{[^}]*font-size: 9\.5px/.test(html));
ok("화면과 서버의 요소가 같다", KEYS.every(k => new RegExp('"key": "' + k + '"').test(py)));

console.log("── ⑤ 뜻풀이는 고정, 사례는 변화 ──");
ok("뜻풀이를 재워 둔다", /_idc_desc_cache/.test(py) && /if ck in _idc_desc_cache/.test(py));
ok("대화문은 매번 새로", /temperature=0\.9/.test(py) && /지난번에 쓴 자리와 겹치지 마라/.test(py));
ok("학술어를 뜻풀이에 못 쓰게 막는다", /화행, 레지스터, 담화[\s\S]{0,120}화계, 상호작용/.test(py));

console.log("── ⑥ 표시할 줄은 학습자 발화 ──");
ok("아니면 가장 가까운 학습자 줄로 옮긴다",
   /if mark < 0 or script\[mark\]\["speaker"\] != "user"/.test(py));

console.log("── ⑦ 학습 기록 ──");
ok("기기 딱지는 익명", /d\" \+ Date\.now\(\)\.toString\(36\)/.test(html) && !/name|email/i.test(/function idcDev[\s\S]*?\n    \}/.exec(html)[0]));
ok("서버에 남긴다", /@app\.post\("\/idc-learn"\)/.test(py));
ok("첫 시도 정답 여부를 남긴다", /"correct": ok, tries: idl\.tries/.test(html) || /correct: ok, tries: idl\.tries/.test(html));
ok("드라이브로 백업한다 (Render 디스크는 지워진다)",
   /_idc_flush/.test(py) && /_gdrive_upload_sync/.test(py) && /Render 의 디스크는 판을 올릴 때마다 지워진다/.test(py));
ok("실패하면 도로 넣어 둔다", /_idc_log\[:0\] = part/.test(py));
ok("연구자용 표가 있다", /@app\.get\("\/idc-stats"\)/.test(py) && /csv=1/.test(py));
ok("/version 에서 상태가 보인다", /"idc": \{/.test(py));

console.log("── ⑧ 형태·사용 (v129) ──");
ok("④ 형태가 ③ 뒤에 온다", paint.indexOf("idl.step === 4") > paint.indexOf("d.meaning"));
ok("문형은 화계를 따른다", /const tier = speechTier\(\)/.test(paint) && /f\[tier\] \|\| f\[1\]/.test(paint));
ok("요소↔문형 표가 있다", /const QUEST_BY_EL = \{/.test(html));
ok("⑤ 사용이 맨 뒤", paint.lastIndexOf("idlBindMic") > paint.indexOf("idl.step === 4"));
ok("★ 방금 들은 대화를 그대로 물려준다 (관찰-가설-실험이 한 흐름)",
   /place: d\.place, script: d\.script/.test(html) && /새 상황을 만들지 마라/.test(py));
ok("발화 연습과 같은 길(\/stt)을 쓴다", /fd\.append\("hint", dr\.text\)/.test(html));
ok("판정도 같은 잣대(simScore)", /simScore\(said, dr\.text\)/.test(html));
ok("학습 대화문이 구어체 규칙을 물려받는다", /\{SPOKEN_RULES\}/.test(py));

console.log("── ⑨ 재생·이전 단추·내 대화 (v130) ──");
/* ★ 예전에는 모든 줄을 한 목소리로 이어 붙이고 간격도 220ms 로 고정이었다.
   들어보기(scPlayAll)가 이미 셋을 다 하고 있었다 — 그대로 쓴다. */
ok("역할마다 다른 목소리", /scMyVoice\(\)/.test(html) && /lines\[i\]\.speaker === "user" \? scMyVoice\(\)/.test(html));
ok("글자 수로 기다린다 (고정 간격 아님)", /900 \+ lines\[i\]\.text\.length \* 165/.test(html));
ok("다음 줄을 미리 받는다", /idlPlayAll[\s\S]{0,1400}ttsPrefetch/.test(html));
ok("재생 중인 줄이 보인다", /\.idl-line\.on \{/.test(html) && /function idlHi/.test(html));
ok("창을 닫으면 소리도 멈춘다", /function idlClose\(\) \{\s*idlHalt\(\);/.test(html));

/* 감추면 있는지 없는지 알 수 없다 — 자리에 두되 흐리게 */
ok("이전 단추를 감추지 않는다", !/prev\.style\.visibility/.test(html)
   && /prev\.disabled = \(idl\.step === 0\)/.test(html));
ok("단추 줄은 늘 손 닿는 자리에", /\.idl-act \{[^}]*position: sticky/.test(html));

/* ★ 학습 대화문을 학습자가 실제로 나눈 대화에서 끌어온다 */
ok("지난 대화에서 발화를 뽑는다", /function idcMineLines/.test(html) && /loadHistory\(\)/.test(html));
/* ★ v132 — 주제 대화 기록만 쓴다. 자유 대화는 자리·상대가 그때그때 달라
   ⓪ 들어가기 한 줄이 서지 않는다. */
ok("주제 대화 기록만 쓴다", /loadHistory\(\)\.filter\(h => h && h\.mode === "rp"\)/.test(html));
ok("기록이 있으면 반드시 거기서", /반드시 거기에서 골라라/.test(py)
   && /기록이 \*\*아예 없을 때뿐\*\*/.test(py));
ok("맞는 대목이 없어도 가장 가까운 것을 쓴다", /가장 가까운 대목을 골라 그 자리에 넣어/.test(py));
ok("그래도 새로 지으면 밖에서 보이게 센다", /_idc_dx\["mine_miss"\] \+= 1/.test(py) && /"miss": _idc_dx\["mine_miss"\]/.test(py));
ok("서버에 함께 보낸다", /mine: idcMineLines\(60\)/.test(html));
ok("서버가 그것을 재료로 쓴다", /실제로 나눈 대화\*\* — 여기서 끌어와라/.test(py));
ok("말은 되도록 그대로 살린다", /말은 되도록 그대로 살려라/.test(py));
ok("기록이 아예 없을 때만 새로 짓는다", /기록이 \*\*아예 없을 때뿐\*\*이다/.test(py));
ok("어디서 왔는지 화면에 알린다", /d\.from === "mine"/.test(html) && /fromMine/.test(html));
ok("서버가 출처를 못 박는다", /frm = "mine" if \(_clean_str\(data\.get\("from"\), 8\) == "mine" and mine_txt\)/.test(py));

console.log("── ⑩ 화면이 실제로 뜨는가 ──");
const dom = new JSDOM(html, { runScripts: "outside-only" });
const D = dom.window.document;
["homeIdcCard", "idcOverlay", "idcCards", "idlOverlay", "idlBody", "idlDots", "idlPrev", "idlNext"]
  .forEach(id => ok("자리 있음 · " + id, !!D.getElementById(id)));
ok("홈 맨 위에 온다",
   D.getElementById("homeIdcCard").compareDocumentPosition(D.getElementById("homeRpCard")) & 4);

console.log(bad ? `\n💥 ${bad}건` : "\n🎉 학습 화면 이상 없음");
process.exit(bad ? 1 : 0);
