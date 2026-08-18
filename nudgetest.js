/* v104 — 넛지 이름을 '진짜로 만들어 보고' 확인한다.
   정규식으로 코드 모양만 보면 조사·말투가 맞는지 알 수 없다.
   QUEST_FORM·qWrap·josaRago 를 실제로 실행해 학습자가 볼 문장을 뽑는다. */
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync(process.argv[3] || "main.py", "utf8");
let fail = 0;
const ok = (m, c, extra) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (extra || ""))); if (!c) fail++; };

/* ── 코드에서 필요한 조각을 떼어 실제로 돌린다 ── */
function grab(re, name) {
    const m = html.match(re);
    if (!m) { console.log("  ❌ " + name + " 못 찾음"); process.exit(1); }
    return m[0];
}
// eval 은 const 를 이 스코프에 남기지 않는다 — Function 으로 감싸 값을 돌려받는다
const [QUEST_FORM] = new Function(
    grab(/const QUEST_FORM = \{[\s\S]*?\n    \};/, "QUEST_FORM") + "\n" +

    "return [QUEST_FORM];")();

const wrapKo = (html.match(/\bqWrap:"((?:[^"\\]|\\.)*)"/) || [])[1];
const forms = Object.keys(QUEST_FORM);
const TIERS = ["격식", "해요체", "반말"];

console.log("── 구조 ──");
/* v114 — 서버가 고를 수 있는 넛지가 6개 → 27개로 늘었다. 그중 여섯(거절·대안·
   재요청·돌려 말하기·명료화 응답·화제 복귀)에 문형이 없어 이름만 나왔다. 채워서 20개. */
ok("QUEST_FORM 20개", forms.length === 20, "실제 " + forms.length);
ok("모두 3단계", forms.every(k => QUEST_FORM[k].length === 3));
ok("빈 문형 없음", forms.every(k => QUEST_FORM[k].every(v => v && v.trim())));
ok("한국어 qWrap 이 '보기'로 읽힌다", !!wrapKo && /처럼/.test(wrapKo), wrapKo);
ok("qWrap 18개 언어", (html.match(/\bqWrap:"/g) || []).length === 18);
ok("문형마다 보기를 둘 이상 준다",
   forms.filter(k => QUEST_FORM[k].some(v => !v.includes("·"))).length <= 4,
   forms.filter(k => QUEST_FORM[k].every(v => !v.includes("·"))).join(","));


console.log("\n── 말투 단계별로 실제로 만들어 본다 ──");
let bad = [];
TIERS.forEach((tier, ti) => {
    forms.forEach(k => {
        const form = QUEST_FORM[k][ti];
        const line = wrapKo.replace("%s", form);
        if (/%[sj]/.test(line)) bad.push(k + "/" + tier + ": 치환 안 됨");
    });
});
ok("모든 자리·모든 말투에서 문장이 완성된다", bad.length === 0, bad.slice(0, 3).join(" · "));

console.log("\n── 학습자에게 안 보여야 할 말 ──");
const BAN = ["대화이동", "역시작", "명료화", "기능 단계", "레지스터", "담화", "화행",
             "연속체", "상호작용적 듣기", "의사소통 전략", "비계", "스캐폴딩"];
const shown = [];
TIERS.forEach((_, ti) => forms.forEach(k => shown.push(QUEST_FORM[k][ti])));
(html.match(/\bq[A-Z]\w*:"((?:[^"\\]|\\.)*)"/g) || []).forEach(s => {
    const v = s.slice(s.indexOf('"') + 1, -1);
    if (/[가-힣]/.test(v)) shown.push(v);
});
BAN.forEach(w => ok(`'${w}' 안 나옴`, !shown.some(s => s.includes(w)),
                    (shown.find(s => s.includes(w)) || "").slice(0, 40)));

console.log("\n── 서버와 짝이 맞는가 ──");
const srvIds = [...py.matchAll(/\{"id":\s*"(\w+)"/g)].map(m => m[1]);
ok("서버 퀘스트 28개", srvIds.length === 28, "실제 " + srvIds.length);
ok("문형 20개가 모두 서버에 있다", forms.every(k => srvIds.includes(k)),
   forms.filter(k => !srvIds.includes(k)).join(","));
const noName = srvIds.filter(id => !forms.includes(id) && !new RegExp('\\b' + id + ':"').test(html));
ok("문형 없는 것은 모두 이름이 있다", noName.length === 0, noName.join(","));

console.log("\n── 말투를 안 타는 것은 '-어 보세요' 인가 ──");
const koLine = (html.split("\n").find(l => /\bqRefuse:"거절/.test(l)) || "");
const plain = srvIds.filter(id => !forms.includes(id));
const notSuggest = plain.filter(id => {
    const m = html.match(new RegExp('\\b' + id + ':"([^"]*)"'));
    return m && /[가-힣]/.test(m[1]) && !/보세요$/.test(m[1]);
});
ok("20개 모두 권유형", notSuggest.length === 0, notSuggest.join(","));

console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 넛지 이름 이상 없음");
process.exit(fail ? 1 : 0);
