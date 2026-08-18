/* v91 — 새로 넣은 여섯 언어가 실제로 도는가 */
const fs = require("fs"), vm = require("vm");
const { JSDOM } = require("jsdom");
const SRC = process.argv[2] || "app.html";
const html = fs.readFileSync(SRC, "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };
const NEW = { ne: "नेपाली", lo: "ລາວ", my: "မြန်မာ", km: "ខ្មែរ", uk: "Українська", ky: "Кыргызча" };

// 사전 선언부부터 마지막 병합 줄까지 잘라 실행
const start = script.indexOf("const I18N = {");
let last = -1, re = /for \(const _l(?:ng)? in I18N_[A-Z0-9]+\) \{[^\n]*\n/g, m;
while ((m = re.exec(script))) last = m.index + m[0].length;
const ctx = { console }; vm.createContext(ctx);
vm.runInContext(script.slice(start, last) + "\nthis.I18N = I18N;", ctx);
const I = ctx.I18N;

console.log("── 사전 ──");
ok(`언어 ${Object.keys(I).length}개`, Object.keys(I).length === 18);
const koKeys = Object.keys(I.ko);
Object.keys(NEW).forEach(c => {
    const d = I[c] || {};
    const miss = koKeys.filter(k => !(k in d));
    const leftKo = koKeys.filter(k => I.ko[k] && d[k] === I.ko[k] && /[가-힣]/.test(String(I.ko[k])));
    ok(`${c}: 열쇠 ${Object.keys(d).length} · 빠짐 ${miss.length} · 한국어 잔존 ${leftKo.length}`,
       miss.length === 0 && leftKo.length <= 2);
});
console.log("── 내용 점검 ──");
ok("한국어 예문(vcSample)은 그대로 둔다", Object.keys(NEW).every(c => (I[c].vcSample || "").includes("호아랑")));
ok("존댓말·반말 용어는 한글을 남긴다", Object.keys(NEW).every(c => (I[c].sgPolite || "").includes("존댓말")));
ok("줄바꿈이 살아 있다", Object.keys(NEW).every(c => (I[c].igStepsIos || "").split("\n").length === 3));
// v115에서 빈 화면 문구가 바뀌며 <br> 이 없어졌다.
ok("empty 문구가 비어 있지 않다", Object.keys(NEW).every(c => (I[c].empty || "").trim().length > 3));

console.log("── 언어 고르기 단추 ──");
const dom = new JSDOM(html);
const d0 = dom.window.document;
["data-lang", "data-iglang", "data-ialang"].forEach(a => {
    const got = [...d0.querySelectorAll(`[${a}]`)].map(b => b.getAttribute(a));
    ok(`${a} ${got.length}개 · 새 언어 6개 다 있음`,
       got.length === 18 && Object.keys(NEW).every(c => got.includes(c)));
});
console.log("── 화면에 실제로 꽂히는가 ──");
const dom2 = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
    beforeParse(w) {
        w.localStorage.setItem("skipEntryGuide", "1");
        w.localStorage.setItem("uiLang", "km");
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
        w.fetch = () => Promise.reject(new Error("no net"));
        w.Element.prototype.scrollIntoView = () => {};
    } });
setTimeout(() => {
    const d = dom2.window.document;
    const sub = (d.getElementById("homeSubEl") || {}).textContent || "";
    const rp = (d.getElementById("hcRpTitleEl") || {}).textContent || "";
    ok(`크메르어로 열면 홈이 크메르어 — "${sub.slice(0, 18)}"`, sub === I.km.homeSub && !!sub);
    ok(`주제 대화 이름도 — "${rp.slice(0, 18)}"`, rp === I.km.hcRpTitle && !!rp);
    console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
    process.exit(fail ? 1 : 0);
}, 800);
