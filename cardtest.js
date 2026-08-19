// ─────────────────────────────────────────────────────────────
// 홈 카드 문구가 실제로 채워지는가 (v131)
//   ★ v128~v130 내내 「한국어 대화 상호작용 능력」 칸이 **비어 있었다.**
//     문구 표(const)가 파일 뒤쪽에 있는데 칠하는 함수는 앞쪽에서 돌아
//     ReferenceError 가 났고, try/catch 가 그것을 삼켰다.
//     문자열 검사로는 못 잡는다 — **실제로 돌려 봐야** 한다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "templates/index.html", "utf8");
let bad = 0;
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();          // 페이지가 뿜는 로그는 조용히
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/",
    virtualConsole: vc,
    beforeParse(w) {
        // 서버가 없으니 통신은 전부 빈손으로 — 화면 그리기만 본다
        w.fetch = () => Promise.resolve({ ok: false, status: 0, json: () => Promise.resolve({}) });
        w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
        w.scrollTo = () => {};
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.load = () => {};
    },
});

setTimeout(() => {
    const d = dom.window.document;
    const txt = (id) => (d.getElementById(id) || {}).textContent || "";
    console.log("── 홈 카드 세 칸이 다 채워졌는가 ──");
    [["hcRpTitleEl", "주제 대화"], ["hcFreeTitleEl", "자유 대화"],
     ["hcIdcTitleEl", "상호작용 능력"]].forEach(([id, what]) => {
        ok(`${what} 이름`, txt(id).trim().length > 0, `"${txt(id)}"`);
    });
    ["hcRpDescEl", "hcFreeDescEl", "hcIdcDescEl"].forEach((id) => {
        ok("설명 · " + id, txt(id).trim().length > 0, `"${txt(id)}"`);
    });
    // jsdom 은 화면 언어가 영어로 잡힌다 — 표에서 한국어 값을 꺼내 본다
    const koName = dom.window.eval("HOME_IDC.ko[0]");
    ok("한국어 이름이 「한국어 대화 상호작용 능력」", koName === "한국어 대화 상호작용 능력", koName);
    ok("열여덟 언어에 다 있다", dom.window.eval("Object.keys(HOME_IDC).length") === 18,
       dom.window.eval("Object.keys(HOME_IDC).length"));

    console.log("── 아이콘이 붙었는가 (이모지 아님) ──");
    const card = d.getElementById("homeIdcCard");
    ok("사다리 아이콘", !!card && !!card.querySelector('use[href="#ic-ladder"]'));
    ok("이모지를 안 쓴다", !!card && !/[\u{1F300}-\u{1FAFF}]/u.test(card.textContent),
       card && card.textContent.trim());
    ["ladder", "idc-move", "idc-topic", "idc-turn", "idc-repair", "idc-strategy",
     "idc-listen", "idc-context", "idc-stage", "idc-nonverbal"].forEach((k) => {
        ok("그림 있음 · " + k, !!d.getElementById("ic-" + k));
    });

    console.log("── 요소 아홉이 다 뜨는가 ──");
    try {
        dom.window.eval("openIdcList()");
        const cards = d.querySelectorAll("#idcCards .idc-card");
        ok("아홉 장", cards.length === 9, cards.length + "장");
/* ★ v133 — 「대화의 흐름 짜기」도 여기서 배운다. 교실은 「몸으로 말하기」 하나뿐. */
        ok("여덟은 배울 수 있다", [...cards].filter(c => !c.disabled).length === 8,
           [...cards].filter(c => !c.disabled).length + "장");
        ok("교실에서 배우는 것은 하나 (몸으로 말하기)",
           [...cards].filter(c => c.disabled).length === 1,
           [...cards].filter(c => c.disabled).length + "장");
        ok("그래도 보이기는 한다(감추지 않는다)",
           [...cards].every(c => !c.classList.contains("hidden")));
        ok("이모지 없음", ![...cards].some(c => /[\u{1F300}-\u{1FAFF}]/u.test(c.textContent)));
        ok("쉬운 이름과 학술어가 둘 다 있다",
           [...cards].every(c => (c.querySelector(".idc-c1") || {}).textContent
                              && (c.querySelector(".idc-c2") || {}).textContent));
    } catch (e) { ok("요소 목록을 열 수 있다", false, e.message); }

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 홈 카드 이상 없음");
    dom.window.close();
    process.exit(bad ? 1 : 0);
}, 1200);
