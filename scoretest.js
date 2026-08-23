// scoretest.js — 점수는 하나여야 한다 (v145)
//
// ★ 왜 이 검사가 있나
//   v59 이전에는 IDC 가 챗봇에 없어서 **기능 단계 진행률로만** 점수를 매겼다.
//   IDC 여덟 요소가 들어온 뒤에도 그 옛 점수가 남아, 결과 화면에 숫자가 두 개
//   떴다. 그런데 「기능 단계의 조직」은 **이미 그 여덟 안에 있다** — 같은 것을
//   두 번 세어 두 자리에 보이고 있었던 셈이다.
//
//   눈금도 다르다. 진행률은 100 을 넘을 수 있는 '과업 달성도'이고
//   IDC 총점은 100점 만점의 '능력 프로파일'이다. 둘 다 「점」이라 부르면
//   학습자는 서로 다른 두 점수로 읽는다.
//
//   그래서 지킬 것은 셋이다.
//     ① 결과 카드의 큰 숫자는 IDC 총점이다
//     ② 같은 화면에 총점이 두 번 뜨지 않는다
//     ③ 「점」이라는 말은 IDC 총점에만 쓴다 (진행률은 %)

const fs = require("fs");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── 점수는 하나다 ────────────────────────────────");

// ① 결과 카드의 큰 숫자 = IDC 총점
const card = [...html.matchAll(/rcScoreVal"\)\.textContent\s*=\s*\n?\s*\(?([^;]+);/g)]
  .map(m => m[1].replace(/\s+/g, " ").trim());
ok("결과 카드가 IDC 총점을 보인다 (" + card.length + "군데)",
   card.length > 0 && card.every(x => /idcTotal/.test(x)),
   "쓰는 값: " + JSON.stringify(card));
ok("결과 카드가 옛 기능단계 점수를 안 쓴다",
   !card.some(x => /rpFinal\.score|rpPercent/.test(x)));

// ② 프로파일 머리줄은 총점 자리가 아니다 — 주제 대화에서는
const fnBody = (html.match(/function renderIdcProfile\([\s\S]*?\n    \}\n/) || [""])[0];
ok("머리줄은 showTotal 일 때만 총점을 찍는다",
   /showTotal/.test(fnBody) && /hSub/.test(fnBody));
// 주제 대화 호출은 showTotal 을 안 준다(=관찰 수만), 자유 대화는 true
const calls = [...html.matchAll(/renderIdcProfile\(([^;]*?)\);/g)].map(m => m[1]);
const rpCalls = calls.filter(c => !/freeIdc/.test(c));
const frCalls = calls.filter(c => /freeIdc/.test(c));
ok("주제 대화 호출은 머리줄에 총점을 안 준다 (" + rpCalls.length + "군데)",
   rpCalls.length > 0 && rpCalls.every(c => !/,\s*true\s*$/.test(c.trim())));
ok("자유 대화 호출은 머리줄이 총점 자리다 (" + frCalls.length + "군데)",
   frCalls.length > 0 && frCalls.every(c => /,\s*true\s*$/.test(c.trim())));

// ③ 「점」은 IDC 에만 — 진행률을 묻는 퀘스트는 %로 말한다
const LANGS = (html.match(/data-lang="[a-z]+"/g) || []).length;
const q150 = [...html.matchAll(/q150:"([^"]*)"/g)].map(m => m[1]);
ok("q150 문구가 지원 언어 전부에 (" + q150.length + "/" + LANGS + ")", q150.length === LANGS);
ok("q150 이 진행률(%)로 말한다", q150.every(x => /%/.test(x)),
   "「점」이 남은 것: " + JSON.stringify(q150.filter(x => !/%/.test(x))));
const q200 = [...html.matchAll(/q200:"([^"]*)"/g)].map(m => m[1]);
ok("q200 도 진행률(%)로 말한다", q200.length === LANGS && q200.every(x => /%/.test(x)));

console.log("\n── 자료도 화면과 같은 값을 남긴다 ────────────────");

// 저장·업로드하는 score 가 화면의 큰 숫자와 같아야 한다
const save = (html.match(/\n\s*score:\s*([^\n]+)/) || ["", ""])[1];
ok("기록에 남기는 score 가 IDC 총점", /idcTotal/.test(save), "지금: " + save.trim());
ok("과업 달성도는 따로 남긴다", /stageScore:/.test(html));

console.log("\n── 서버 쪽 근거 ─────────────────────────────────");

// 기능 단계가 IDC 여덟 요소 안에 있다는 것이 이 손질의 근거다.
// 이게 깨지면(stage 를 IDC 에서 빼면) 점수를 도로 둘로 갈라야 한다.
const first = (py.match(/IDC_ELEMENTS = \[[\s\S]{0,300}?"key":\s*"(\w+)"/) || [])[1];
ok("기능 단계가 IDC 요소 안에 있다 (key=" + first + ")", first === "stage",
   "stage 가 IDC 밖으로 나가면 점수를 다시 갈라야 합니다");
ok("점수 대상에서 안 빠졌다",
   /IDC_SCORED_KEYS = \[e\["key"\] for e in IDC_TRAINABLE\]/.test(py)
   && /"key":\s*"stage",\s*"layer":\s*"macro",\s*"media":\s*"ai"/.test(py));

console.log();
if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
console.log("🎉 점수는 하나입니다 — IDC 총점 100점");
