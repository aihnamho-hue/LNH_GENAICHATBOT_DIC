// nativetest.js — 언어를 바꾸면 한국어만 남는 자리가 없어야 한다 (v146)
//
// ★ 왜 이 검사가 있나
//   몽골어로 바꾸고 「한국어 대화를 잘 하는 방법」에 들어가면 제목만 번역되고
//   요소 이름·대화문·단계 이름은 한국어로 남아 있었다. 무엇을 배우는 자리인지
//   **골라서 들어가 보기 전에는 알 수 없다.**
//
//   한국어 이름은 지운다는 뜻이 아니다 — 그것도 배울 말이다. **병기**한다.
//
// 지킬 것
//   ① 요소 카드에 모국어가 붙는다 (한국어로 보면 안 붙는다)
//   ② 학습 대화문이 주제 대화와 같은 꼴이고, 줄마다 모국어 자리가 있다
//   ③ 대화문 줄을 누르면 모국어가 펼쳐진다
//   ④ 아홉 요소 모두 지원 언어 전부에 번역이 있다

const fs = require("fs");
const html = fs.readFileSync("app.html", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};
const LANGS = (html.match(/data-lang="[a-z]+"/g) || []).length;

console.log("── ① 요소 카드에 모국어 병기 ─────────────────────");

const cards = (html.match(/function renderIdcCards\(\)[\s\S]*?\n    \}\n/) || [""])[0];
ok("카드가 모국어를 붙인다", /idc-c2"\)\.textContent\s*=[\s\S]{0,120}t\("idc_"/.test(cards));
ok("한국어로 보면 안 붙인다", /uiLang\s*!==\s*"ko"/.test(cards),
   "한국어에서는 같은 말이 두 줄이 된다");
ok("모국어 줄이 얇다", /\.idc-c2\s*\{[^}]*font-weight:\s*400/.test(html));
ok("비었으면 자리를 안 차지한다", /\.idc-c2:empty\s*\{[^}]*display:\s*none/.test(html));

console.log("\n── ② 아홉 요소 번역이 다 있다 ────────────────────");

const KEYS = ["move", "topic", "turn", "repair", "strategy",
              "listen", "context", "stage", "nonverbal"];
KEYS.forEach(k => {
  const n = (html.match(new RegExp("idc_" + k + ':"', "g")) || []).length;
  ok(`idc_${k} (${n}/${LANGS})`, n === LANGS);
});
// 카드가 쓰는 열쇠와 표에 있는 열쇠가 어긋나면 빈칸이 뜬다
const lesKeys = [...((html.match(/const IDC_LES = \[[\s\S]*?\n    \];/) || [""])[0])
  .matchAll(/key:\s*"(\w+)"/g)].map(m => m[1]);
ok("IDC_LES 의 모든 요소에 번역이 있다 (" + lesKeys.length + "개)",
   lesKeys.length > 0 && lesKeys.every(k => KEYS.includes(k)),
   "번역 표에 없는 요소: " + JSON.stringify(lesKeys.filter(k => !KEYS.includes(k))));

console.log("\n── ③ 학습 대화문이 주제 대화와 같은 꼴 ───────────");

const idlS = (html.match(/function idlScript\(lit\)[\s\S]*?\n    \}\n/) || [""])[0];
ok("주제 대화와 같은 클래스를 쓴다",
   /"sc-line/.test(idlS) && /sc-who/.test(idlS) && /sc-text/.test(idlS));
ok("줄마다 모국어 자리가 있다", /sc-native/.test(idlS) && /l\.native/.test(idlS));
ok("누르면 모국어가 펼쳐진다", /classList\.toggle\("open"\)/.test(idlS));
ok("누르면 그 줄만 다시 들린다", /ttsPlay\(l\.text/.test(idlS));
ok("두 판짜기가 안 싸운다 (옛 규칙을 좁혔다)",
   /\.idl-line:not\(\.sc-line\)\s*\{/.test(html),
   ".idl-line 옛 규칙이 .sc-line 을 덮어씁니다");
// 주제 대화 쪽도 같은 장치를 그대로 쓰고 있는가 (한쪽만 고치면 또 어긋난다)
const scR = (html.match(/function renderScript\(\)[\s\S]*?\n    \}\n/) || [""])[0];
ok("주제 대화도 같은 장치", /sc-native/.test(scR) && /classList\.toggle\("open"\)/.test(scR));

console.log("\n── ④ 기능 단계 이름도 병기 ───────────────────────");

ok("단계 이름에 모국어를 붙인다", /sc-st-native/.test(scR) && /st\.native/.test(scR));
ok("한국어로 보면 안 붙인다", /st\.native && uiLang && uiLang !== "ko"/.test(scR));
ok("모국어 줄이 얇다", /\.sc-st-native\s*\{[^}]*font-weight:\s*400/.test(html));

console.log("\n── ⑤ 줄 사이 틈 (v146) ──────────────────────────");

// ttsPlay 가 소리 끝까지 기다리는데 그 뒤에 또 글자수만큼 기다리면 두 번 쉬는 셈이다
ok("틈이 한 곳에서 정해진다", /const SC_GAP\s*=\s*\d+/.test(html));
const gap = parseInt((html.match(/const SC_GAP\s*=\s*(\d+)/) || [])[1] || "9999", 10);
ok("틈이 1초 아래다 (" + gap + "ms)", gap > 0 && gap < 1000);
ok("두 화면이 같은 값을 쓴다",
   (html.match(/wait\s*=\s*SC_GAP;/g) || []).length >= 1
   && /return SC_GAP;/.test(html));
ok("글자수로 또 기다리지 않는다",
   !/900 \+ (?:line|lines\[i\])\.text\.length \* 165/.test(html),
   "재생을 기다린 뒤 글자수만큼 또 기다리는 자리가 남았습니다");

console.log("\n── ⑥ 학습 화면 문구가 지원 언어 전부에 (v147) ──");

// ★ IDC_TXT 에 ko·en 둘뿐이어서 스페인어로 봐도 「Hold to talk」가 영어로 뜬다.
//   표 하나만 빠져도 화면 전체가 영어가 된다 — 개수가 아니라 **빠진 언어가 있는가**를 잰다.
const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map(m => m[1]))];
function tableLangs(name) {
  const m = html.match(new RegExp("const " + name + "\\s*=\\s*\\{"));
  if (!m) return null;
  const start = m.index + m[0].length;
  const end = html.indexOf("\n    };", start);
  const seg = html.slice(start, end);
  return new Set([...seg.matchAll(/[\{\s,]([a-z]{2}):\s*[\"\{\[]/g)].map(x => x[1]));
}
["IDC_TXT", "VP_TXT", "STT_MSG", "NZ_NOW", "HOME_IDC", "MK_MSG"].forEach(name => {
  const got = tableLangs(name);
  if (!got) { ok(name + " 표가 있다", false); return; }
  const miss = codes.filter(c => !got.has(c));
  ok(`${name} (${got.size}/${codes.length})`, miss.length === 0, "빠진 언어: " + JSON.stringify(miss));
});
// t() 가 없는 열쇠를 영어로 떨어뜨리므로, 열쇠 수도 한국어와 같아야 한다
const idcSeg = (() => {
  const m = html.match(/const IDC_TXT\s*=\s*\{/);
  return html.slice(m.index, html.indexOf("\n    };", m.index));
})();
const perLang = [...idcSeg.matchAll(/\n\s{8}([a-z]{2}):\s*\{/g)];
const counts = perLang.map((m, i) => {
  const seg = idcSeg.slice(m.index, i + 1 < perLang.length ? perLang[i + 1].index : undefined);
  return [m[1], new Set([...seg.matchAll(/(\w+):\s*[\"\[]/g)].map(x => x[1])).size];
});
const koN = (counts.find(c => c[0] === "ko") || [])[1];
const short = counts.filter(c => c[1] < koN);
ok(`IDC_TXT 열쇠 수가 한국어(${koN})와 같다`, short.length === 0,
   "모자란 언어: " + JSON.stringify(short));

console.log("\n── ⑦ 대화문 줄이 좌우로 나뉩니다 ──────────────");

ok("호아랑은 왼쪽", /\.sc-line\s*\{[^}]*margin-right:\s*auto/.test(html));
ok("학습자는 오른쪽", /\.sc-line\.mine\s*\{[^}]*margin-left:\s*auto/.test(html)
   && /\.sc-line\.mine\s*\{[^}]*text-align:\s*right/.test(html));
ok("한쪽이 비어 보인다 (너비 100% 아님)", /\.sc-line\s*\{[^}]*width:\s*8\d%/.test(html));

console.log();
if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
console.log("🎉 모국어가 끝까지 따라갑니다");
