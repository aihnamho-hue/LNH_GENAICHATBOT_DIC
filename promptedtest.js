// promptedtest.js — 「지시받고 해낸 것」이 맞게 잡히고 맞게 적히는가 (v154)
//
// ★ 왜 이 검사가 있나
//   이 줄은 제5장에서 **비계가 실제로 작동했는가**를 말하는 자리다.
//   시켜서 한 것과 스스로 한 것이 섞이면 페이딩 논의가 통째로 무너진다.
//
//   두 가지가 실제로 틀어져 있었다.
//   ① 요소 이름이 **학습자의 화면 언어**로 찍혔다. 중국어로 배우는 학습자의
//     기록에는 중국어로 남았다 — 40편을 나란히 놓고 셀 수 없다.
//   ② 판이 끝나면 서버가 새 숫자를 보내는데, 대화록은 **60초마다** 만들어
//     올라간다. 그 사이의 저장본은 내내 **지난 판의 숫자**를 달고 갔다.

const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── ① 서버가 세는 방법 ──────────────────────────");

// 개입을 보낸 그 자리에서 「몇 차례째였나」를 찍어 둔다
ok("개입할 때 그 시점의 차례를 적어 둔다",
   /idc_state\["intv_turn"\]\[el\] = turns/.test(py));
// 실현이 들어오면 그 표시와 견준다
ok("실현이 오면 그 표시와 견준다",
   /t0 = idc_state\["intv_turn"\]\.get\(k\)/.test(py));
const win = (py.match(/turn_now - t0 <= (\d+)/) || [])[1];
ok(`창이 몇 차례인가 (${win}차례)`, win === "4",
   "분석은 몇 차례 지난 뒤에야 돈다. 좁으면 지시받고 한 것이 자발로 잡힌다");
ok("한 번 세면 표시를 지운다",
   /idc_state\["prompted"\]\[k\] \+= 1[\s\S]{0,120}intv_turn"\]\.pop\(k, None\)/.test(py),
   "안 지우면 개입 하나에 실현이 여러 번 붙는다");
ok("실현으로 셀 때만 올린다 — 누적보다 클 수 없다",
   /idc_state\["counts"\]\[k\] \+= 1[\s\S]{0,700}idc_state\["prompted"\]\[k\] \+= 1/.test(py),
   "counts 를 올리는 같은 자리 안에서만 prompted 가 오른다");

// ★ 두 곳이 같은 눈금을 써야 한다. 하나는 초, 하나는 차례면 견줄 수가 없다
const marks = [...py.matchAll(/turns = _user_turns\(\)|turn_now = _user_turns\(\)/g)].length;
ok(`양쪽 다 학습자 차례로 잰다 (${marks}곳)`, marks >= 2,
   "찍을 때와 견줄 때가 다른 눈금이면 창의 뜻이 사라진다");

ok("총점에 드는 요소만 센다",
   /"prompted": \{k: 0 for k in IDC_SCORED_KEYS\}/.test(py),
   "비언어적 행위는 총점 밖이다(v59) — 여기에도 끼면 안 된다");
ok("판이 끝날 때 화면으로 보낸다", /"idcPrompted": dict\(idc_state\["prompted"\]\)/.test(py));

console.log("\n── ② 화면이 지난 판을 안 물고 가는가 ───────────");
ok("판을 시작할 때 지운다",
   /transcriptLog = \[\];[\s\S]{0,600}LAST_PROMPTED = null;\s*\n\s*LAST_INTV = 0;/.test(html),
   "대화록을 지우는 그 자리에서 함께 지워야 한다");
ok("대화록은 한국어 이름을 쓴다",
   /koIdc\(k\) \+ " " \+ LAST_PROMPTED\[k\]/.test(html) && /function koIdc/.test(html));
ok("koIdc 는 화면 언어를 안 본다",
   /function koIdc\(key\) \{\s*\n?\s*return \(I18N\.ko/.test(html),
   "I18N[uiLang] 을 거치면 다시 학습자 언어가 된다");

console.log("\n── ③ 실제로 돌려 본다 ──────────────────────────");
const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/",
  beforeParse(w) {
    w.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve("") });
    w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
    w.scrollTo = () => {};
    w.HTMLElement.prototype.scrollIntoView = () => {};
    w.HTMLMediaElement.prototype.play = () => Promise.resolve();
    w.HTMLMediaElement.prototype.pause = () => {};
    w.HTMLMediaElement.prototype.load = () => {};
    w.open = () => null;
    try { w.localStorage.setItem("uiLang", "zh"); w.localStorage.setItem("userName", "王小明"); } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const P = (s) => { try { return w.eval(s); } catch (e) { return "ERR " + e.message; } };

  // 아홉 요소가 모두 한국어 이름을 가지고 있는가
  const keys = ["stage", "topic", "move", "turn", "repair", "strategy", "listen", "context", "nonverbal"];
  const miss = keys.filter((k) => {
    const v = P(`koIdc(${JSON.stringify(k)})`);
    return !v || v === k || !/[가-힣]/.test(v);
  });
  ok(`아홉 요소가 다 한국어 이름을 가진다 (${keys.length - miss.length}/${keys.length})`,
     miss.length === 0, "이름 없는 요소: " + JSON.stringify(miss));

  // 화면 언어를 중국어로 두고 대화록을 만들어 본다
  P('uiLang = "zh"');
  ok("화면은 중국어로 뜬다", /[一-鿿]/.test(P('t("idc_topic")')), P('t("idc_topic")'));
  ok("★ 기록은 그래도 한국어", /[가-힣]/.test(P("koIdc('topic')"))
     && !/[一-鿿]/.test(P("koIdc('topic')")), P("koIdc('topic')"));

  P('sessionStartedAt = new Date()');
  P('transcriptLog = [{ role:"user", text:"안녕하세요", time:"00:01" }]');
  P('LAST_PROMPTED = { topic: 2, repair: 1, turn: 0 }');
  P('LAST_INTV = 3');
  const txt = P("buildTranscriptText()");
  const line = String(txt).split("\r\n").find((l) => l.indexOf("지시받고 해낸 것") >= 0) || "";
  console.log("     " + line.trim());
  ok("그 줄이 있다", !!line);
  ok("한자가 없다", !/[一-鿿]/.test(line), line);
  ok("0 인 요소는 안 적는다", line.indexOf("말차례") < 0, "해내지 않은 것을 적으면 셈이 부풀어 오른다");
  ok("횟수가 함께 간다", /2/.test(line) && /1/.test(line));
  ok("개입 횟수도 적힌다", /교육적 개입: 3회/.test(String(txt)));

  // 지난 판의 숫자가 남아 있으면 어떻게 되는지 — 지우면 그 줄이 사라져야 한다
  P("LAST_PROMPTED = null; LAST_INTV = 0;");
  const txt2 = String(P("buildTranscriptText()"));
  ok("지우면 그 줄이 사라진다", txt2.indexOf("지시받고 해낸 것") < 0,
     "지난 판의 숫자가 남으면 개입 없던 판에도 이 줄이 찍힌다");
  ok("개입 0회로 적힌다", /교육적 개입: 0회/.test(txt2));

  console.log();
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 「지시받고 해낸 것」이 맞게 잡히고 한국어로 남습니다");
  process.exit(0);
}, 900);
