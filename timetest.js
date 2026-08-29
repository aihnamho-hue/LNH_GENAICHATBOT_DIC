// timetest.js — 한 판 10분 · 1분 전 알림 · 넛지 눌러 닫기 (v150)
//
// ★ 왜 이 검사가 있나
//   50명 수업에서 두 학생이 한 대를 쓰며 질질 끌다 10분을 넘겼다.
//   비용은 판 수가 아니라 **말한 시간**이 정하므로 여기가 가장 곧은 손잡이다.
//
//   ★★ 가장 조심할 곳 — **끝내는 길이 하나여야 한다.**
//     시간이 다 됐다고 따로 끊으면(웹소켓을 먼저 닫으면) 결과·총평·기록이
//     전부 날아간다. 학습자가 「대화 종료하기」를 누른 것과 **같은 함수**를
//     불러야 한다. 이 검사가 그 자리를 지킨다.

const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── ① 시계가 제대로 걸리는가 ─────────────────────");

const lim = parseInt((html.match(/const TALK_LIMIT_MS\s*=\s*([\d\s*]+);/) || [])[1]
  ? eval((html.match(/const TALK_LIMIT_MS\s*=\s*([\d\s*]+);/) || [])[1]) : 0, 10);
const warn = (html.match(/const TALK_WARN_MS\s*=\s*([\d\s*]+);/) || [])[1]
  ? eval((html.match(/const TALK_WARN_MS\s*=\s*([\d\s*]+);/) || [])[1]) : 0;
ok(`한 판 상한이 10분 (${lim / 60000}분)`, lim === 600000);
ok(`알림이 1분 전 (${warn / 1000}초)`, warn === 60000);

const clk = (html.match(/function talkClockStart\(\)[\s\S]*?\n    \}\n/) || [""])[0];
ok("먼저 옛 시계를 푼다", /talkClockStop\(\);/.test(clk),
   "안 풀면 시계가 겹쳐 두 번 끊긴다");

// ★★ 끝내는 길이 하나인가 — 이 검사가 이 판의 핵심이다
ok("10분에 「대화 종료하기」와 같은 함수를 부른다",
   /endRoleplaySession\(\)/.test(clk) && /endFreeSession\(\)/.test(clk),
   "따로 끊으면 결과·총평·기록이 날아간다");
ok("두 갈래를 가른다", /rpSessionActive/.test(clk));
ok("따로 소켓을 닫지 않는다",
   !/ws\.close|stopSession\(\)/.test(clk),
   "여기서 소켓을 닫으면 총평이 영영 안 온다");

console.log("\n── ② 시계를 푸는 자리 ───────────────────────────");

const stops = (html.match(/talkClockStop\(\);/g) || []).length;
ok(`푸는 자리가 넷 이상 (${stops})`, stops >= 4);
const inFn = (name) => {
  const m = html.match(new RegExp("function " + name + "\\(\\)[\\s\\S]*?\\n    \\}\\n"));
  return m ? /talkClockStop\(\)/.test(m[0]) : false;
};
ok("stopSession 에서 푼다", inFn("stopSession"), "다음 판이 곧바로 끊긴다");
ok("endRoleplaySession 에서 푼다", inFn("endRoleplaySession"), "두 번 끝난다");
ok("endFreeSession 에서 푼다", inFn("endFreeSession"), "두 번 끝난다");
ok("대화가 시작되면 건다",
   /sessionStartedAt = new Date\(\);\s*\n\s*talkClockStart\(\);/.test(html));

console.log("\n── ③ 남은 시간 알림이 지원 언어 전부에 ───────────");

const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map(m => m[1]))];
const seg = (() => {
  const m = html.match(/const TL_MSG\s*=\s*\{/);
  return m ? html.slice(m.index, html.indexOf("\n    };", m.index)) : "";
})();
const got = new Set([...seg.matchAll(/\n\s+([a-z]{2}):\s*\{/g)].map(m => m[1]));
ok(`TL_MSG (${got.size}/${codes.length})`, codes.every(c => got.has(c)),
   "빠진 언어: " + JSON.stringify(codes.filter(c => !got.has(c))));
["warn", "warnSub", "over"].forEach(k => {
  const n = (seg.match(new RegExp(k + ":\"", "g")) || []).length;
  ok(`${k} (${n}/${codes.length})`, n === codes.length);
});

console.log("\n── ④ 넛지를 눌러서 닫는가 (실제로 눌러 본다) ────");

const vc = new VirtualConsole();
const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/",
  virtualConsole: vc,
  beforeParse(w) {
    w.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve("") });
    w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
    w.scrollTo = () => {};
    w.HTMLElement.prototype.scrollIntoView = () => {};
    w.HTMLMediaElement.prototype.play = () => Promise.resolve();
    w.HTMLMediaElement.prototype.pause = () => {};
    try { w.localStorage.setItem("uiLang", "ko"); w.localStorage.setItem("userName", "바트"); } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const d = w.document;
  const el = d.getElementById("hamPeek");
  ok("빼꼼 자리가 있다", !!el);
  if (el) {
    // 넛지를 하나 띄운다
    try { w.eval('hamPeekHtml("지금이에요.", "거절해 보세요!", 5600, "nz")'); }
    catch (e) { ok("넛지를 띄울 수 있다", false, e.message); }
    ok("넛지가 떴다", el.classList.contains("show"));
    // 떠 있는 동안에는 눌리는가 (pointer-events)
    ok("떠 있을 때만 눌린다 (CSS)",
       /\.ham-peek\.show\s*\{[^}]*pointer-events:\s*auto/.test(html)
       && /\.ham-peek\s*\{[^}]*pointer-events:\s*none/.test(html),
       "늘 켜 두면 안 보이는 말풍선이 마이크 단추를 가로챈다");
    // 눌러 본다
    el.click();
    ok("★ 누르면 바로 사라진다", !el.classList.contains("show"));
    // 안 떠 있을 때 눌러도 탈이 없어야 한다
    try { el.click(); ok("안 떠 있을 때 눌러도 괜찮다", true); }
    catch (e) { ok("안 떠 있을 때 눌러도 괜찮다", false, e.message); }
  }

  console.log("\n── ⑤ 시계 함수가 실제로 도는가 ─────────────────");
  // setTimeout 을 가로채 **몇 초 뒤에 걸리는지**만 본다 (10분을 기다릴 수는 없다)
  const delays = [];
  const realST = w.setTimeout;
  w.setTimeout = (fn, ms) => { delays.push(ms); return realST(() => {}, 0); };
  try { w.eval("talkClockStart()"); } catch (e) { ok("talkClockStart 를 부를 수 있다", false, e.message); }
  w.setTimeout = realST;
  ok("두 개를 건다 (알림 · 종료)", delays.length === 2, JSON.stringify(delays));
  ok("알림이 9분에 (" + (delays[0] / 60000) + "분)", delays[0] === 540000);
  ok("종료가 10분에 (" + (delays[1] / 60000) + "분)", delays[1] === 600000);

  console.log();
  // jsdom 이 앱의 타이머를 물고 있어 그냥 두면 프로세스가 안 끝난다
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 한 판은 10분, 끝내는 길은 하나입니다");
  process.exit(0);
}, 700);
