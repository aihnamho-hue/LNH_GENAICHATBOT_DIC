// histlearntest.js — 지난 대화가 복습 자리가 되었는가 (v156)
//
// ★ 왜 이 검사가 있나
//   지난 대화는 **읽을 글 덩어리**였다. 다시 열어도 대화만 있고,
//   그 판에서 무엇을 해냈고 다음에 무엇을 해 볼지가 없었다.
//   기록을 다시 보는 일이 학습이 되려면 셋이 함께 있어야 한다 —
//   ① 그때의 총평 ② 요소별로 무엇을 해냈나 ③ 다음에 써 볼 한 마디.
//
// ★ 그리고 셋 다 **판이 끝날 때 이미 받아 둔 것**이어야 한다.
//   다시 열 때마다 서버를 부르면 판마다 돈이 더 든다.

const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── ① 서버가 같은 호출에서 함께 준다 ────────────");
ok("프로파일 프롬프트에 phrases 칸이 있다",
   /"phrases":\[\{\{"key":"","say":"","when":""\}\}\]/.test(py));
ok("아쉬운 것부터 고르라고 못 박았다", /가장 아쉬운 것부터/.test(py));
ok("없던 상황을 지어내지 말라고 했다", /지어내지 마라/.test(py));
ok("문법 설명을 막았다", /문법 설명을 하지 마라/.test(py));
ok("셋만 받는다", /\(data or \{\}\)\.get\("phrases"\) or \[\]\)\[:3\]/.test(py));
ok("모르는 열쇠는 비운다", /k if k in idc_state\["counts"\] else ""/.test(py));
ok("final_score 로 함께 내려간다", /"phrases": idc\.get\("phrases"\) or \[\]/.test(py));
ok("추가 호출이 없다", !/_gen_json[^\n]*phrase/i.test(py),
   "따로 부르면 판마다 돈이 더 든다");

console.log("\n── ② 화면이 기기에 함께 남긴다 ─────────────────");
ok("final_score 에서 받는다", /phrases: msg\.phrases \|\| \[\]/.test(html));
ok("지난 대화에 learn 을 함께 적는다",
   /turns, quests, stats, learn \}\)/.test(html));
["review", "idc", "idcTotal", "phrases", "prompted"].forEach((k) => {
  ok(`learn 에 ${k} 가 있다`, new RegExp("const learn = \\{[\\s\\S]{0,400}" + k + ":").test(html));
});

console.log("\n── ③ 복습 카드가 대화 앞에 온다 ────────────────");
ok("펼칠 때 앞에 끼운다", /body\.insertBefore\(card, body\.firstChild\)/.test(html),
   "대화 글부터 나오면 그대로 다시 읽고 만다");
ok("두 번 만들지 않는다", /!body\.querySelector\("\.hlrn"\)/.test(html));
ok("결과 화면과 같은 꼴을 쓴다", /row\.className = "idc-row"/.test(html.split("function buildLearnCard")[1] || ""),
   "두 곳이 다르게 생기면 학습자가 두 번 배워야 한다");
{
  const seg = html.match(/const RVW_TXT = \{[\s\S]*?\n    \};/);
  const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map((m) => m[1]))];
  const has = new Set([...(seg ? seg[0] : "").matchAll(/[\{\s,]([a-z]{2}):\s*\{/g)].map((x) => x[1]));
  ok(`「다음에 이렇게」가 지원 언어 전부에 (${has.size}/${codes.length})`,
     codes.every((c) => has.has(c)), "빠진 언어: " + JSON.stringify(codes.filter((c) => !has.has(c))));
}

console.log("\n── ④ 실제로 열어 본다 ─────────────────────────");
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
    const hist = [
      { ts: "2026-08-30T08:00:00.000Z", mode: "free", title: "자유 대화",
        preview: "…", text: "[00:01] 나:\n  안녕하세요\n", turns: [],
        learn: {
          review: "카페 이야기를 먼저 꺼낸 것이 좋았어요. 다음에는 모르는 말이 나왔을 때 되물어 보세요.",
          idcTotal: 72,
          idc: [{ key: "topic", grade: "hi", why: "카페 이야기를 먼저 꺼냈어요", scored: true },
                { key: "repair", grade: "lo", why: "막혔을 때 되물어 보세요", scored: true }],
          phrases: [{ key: "repair", say: "그게 뭐라고 하죠?", when: "단어가 생각 안 날 때" },
                    { key: "turn", say: "잠깐만요, 제가 말해 볼게요.", when: "내 차례를 잡을 때" }],
          prompted: { repair: 1 }, intv: 2,
        } },
      // v156 앞의 기록 — learn 이 없다. 그래도 깨지면 안 된다
      { ts: "2026-08-29T08:00:00.000Z", mode: "rp", title: "옛 기록",
        preview: "…", text: "[00:01] 나:\n  네\n", turns: [] },
    ];
    try {
      w.localStorage.setItem("uiLang", "ko");
      w.localStorage.setItem("masamasaHistory", JSON.stringify(hist));
    } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const d = w.document;
  const P = (s) => { try { return w.eval(s); } catch (e) { return "ERR " + e.message; } };

  // 홈 가운데를 눌러 지난 대화가 열리는가 (v156 ②)
  P('document.getElementById("homeHeroTap").click()');
  ok("홈 가운데를 누르면 지난 대화가 열린다",
     !d.getElementById("histOverlay").classList.contains("hidden"),
     "오른쪽 위 작은 시계 단추는 학습자가 잘 못 찾는다");

  const rows = [...d.querySelectorAll("#histList .hist-item")];
  ok(`기록 둘이 보인다 (${rows.length})`, rows.length === 2);

  rows[0].click();                                  // 첫 기록을 펼친다
  const card = rows[0].querySelector(".hlrn");
  ok("복습 카드가 생겼다", !!card);
  if (card) {
    const txt = card.textContent || "";
    ok("총평이 있다", /카페 이야기를 먼저 꺼낸 것이 좋았어요/.test(txt));
    ok("요소 이름이 보인다", /이야깃거리 이끌기/.test(txt) && /막혔을 때 되살리기/.test(txt));
    ok("판정이 보인다", (card.querySelectorAll(".idc-grade").length === 2));
    ok("총점이 보인다", /72/.test(txt));
    ok("다음에 써 볼 말이 있다", /그게 뭐라고 하죠\?/.test(txt));
    ok("언제 쓰는지도 있다", /단어가 생각 안 날 때/.test(txt));
    ok("대화 글보다 앞에 있다",
       card === rows[0].querySelector(".hi-body").firstChild,
       "무엇을 배웠는지가 먼저 와야 다시 읽는 일이 학습이 된다");
    ok("대화 글도 그대로 남아 있다", /안녕하세요/.test(rows[0].querySelector(".hi-body").textContent));
  }

  rows[0].click(); rows[0].click();                 // 접었다 다시 편다
  ok("두 번 펼쳐도 카드가 하나뿐",
     rows[0].querySelectorAll(".hlrn").length === 1);

  // 옛 기록 — learn 이 없다
  rows[1].click();
  ok("옛 기록은 카드 없이 그냥 열린다",
     !rows[1].querySelector(".hlrn") && /네/.test(rows[1].querySelector(".hi-body").textContent),
     "v156 앞의 기록에는 남겨 둔 것이 없다 — 깨지지만 않으면 된다");

  // 화면 언어를 바꿔도 이름이 따라오는가
  P('uiLang = "vi"');
  const c2 = P('(function(){ var c = buildLearnCard(loadHistory()[0]); return c ? c.textContent : ""; })()');
  ok("모국어로도 나온다 (" + String(c2).slice(0, 28) + "…)",
     /Lần sau/.test(String(c2)) && !/다음에 이렇게/.test(String(c2)));

  console.log();
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 지난 대화가 복습 자리가 되었습니다");
  process.exit(0);
}, 900);
