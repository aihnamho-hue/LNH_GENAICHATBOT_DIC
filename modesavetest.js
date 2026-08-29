// modesavetest.js — 주제 대화가 「자유」로 저장되면 안 된다 (v151)
//
// ★ 왜 이 검사가 있나
//   실전 50명 수업 뒤 드라이브를 보니 **주제 대화가 전부 「자유」로** 저장돼 있었다.
//   그런데 그 파일을 열어 보면 안쪽 머리글에는 「모드: 주제 대화(상황극)」라 적혀 있다.
//
//   같은 판을 **두 눈금으로 재고 있었다** —
//     파일 이름  ← mode            (홈에서 카드를 고를 때 정해지는 화면 상태)
//     머리글     ← rpSessionActive (대화가 붙을 때 정해지고 내내 안 바뀜)
//
//   연구 자료가 오염되는 자리다. 주제 대화 자료가 자유 대화에 섞이면
//   뒷날 갈라낼 방법이 없다.

const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── ① 화면이 한 눈금만 쓰는가 ────────────────────");

const sm = (html.match(/function sessionMode\(\)[\s\S]*?\n    \}/) || [""])[0];
ok("sessionMode 가 rpSessionActive 를 먼저 본다",
   /rpSessionActive && rpPlan/.test(sm),
   "mode 만 보면 홈 상태가 흔들릴 때 어긋난다");
ok("meta 도 같은 눈금을 쓴다",
   /mode:\s*sessionMode\(\)/.test(html),
   "meta 와 파일 이름이 따로 놀면 안 된다");
ok("meta 가 옛 눈금을 안 쓴다",
   !/mode:\s*\(mode === "rp" \? "rp" : "free"\)/.test(html));
// 파일 이름·meta 둘 다 이 한 함수에서 나와야 한다
ok("업로드가 sessionMode() 를 보낸다",
   /fd\.append\("mode", sessionMode\(\)\)/.test(html));

console.log("\n── ② 서버가 못 받았을 때 「자유」로 단정하지 않는가 ──");

ok("「미상」이라는 갈래가 있다", /"미상"/.test(py),
   "못 받았으면 못 받았다고 적어야 뒷날 걸러 낼 수 있다");
ok("meta 의 mode 도 본다", /_m\.get\("mode"\)/.test(py));
ok("계획(roleplay)이 있으면 주제로 본다", /_m\.get\("roleplay"\)/.test(py));
ok("못 받으면 로그를 남긴다", /mode 를 못 받았다/.test(py));
ok("빈 값이 곧바로 「자유」가 되지 않는다",
   !/\.get\(\(mode or ""\)\.strip\(\), "자유"\)/.test(py));

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
    try { w.localStorage.setItem("uiLang", "ko"); w.localStorage.setItem("userName", "바트"); } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const P = (s) => { try { return w.eval(s); } catch (e) { return "ERR " + e.message; } };

  ok("처음에는 자유", P("setMode('free'); sessionMode()") === "free");
  ok("주제 대화를 고르면 주제", P("setMode('rp'); sessionMode()") === "rp");

  /* ★★ 실제로 어긋났던 자리 —
     계획이 살아 있는데 홈 상태(mode)만 「free」로 되돌아간 경우.
     예전에는 여기서 「자유」가 나와 파일 이름이 틀렸다. */
  const mixed = P(`
    rpSessionActive = true;
    rpPlan = { topic_ko: "친구 고민 상담", goal_ko: "조언", place_ko: "교실",
               user_role: "친구", ai_role: "친구", stages: [] };
    mode = "free";                    // 홈 상태만 되돌아간 상황
    sessionMode();
  `);
  ok("★ 계획이 있으면 홈 상태가 free 여도 「주제」", mixed === "rp", "얻은 것: " + mixed);
  ok("meta 도 같이 「주제」", P("buildSessionMeta().mode") === "rp",
     "얻은 것: " + P("buildSessionMeta().mode"));

  // 자유 대화는 계획이 없으므로 그대로 자유여야 한다
  const free = P("rpSessionActive = false; rpPlan = null; mode = 'free'; sessionMode()");
  ok("자유 대화는 그대로 자유", free === "free", "얻은 것: " + free);

  console.log();
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 주제 대화는 「주제」로 저장됩니다");
  process.exit(0);
}, 800);
