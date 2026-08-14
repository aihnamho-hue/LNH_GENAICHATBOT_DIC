/* 지난 대화 — 전체 목록 · 자리에서 펼치기/접기 (v87) */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

const seed = [];
for (let i = 0; i < 7; i++) seed.push({
    ts: new Date(2026, 7, 1 + i).toISOString(), mode: i % 2 ? "rp" : "free",
    title: "대화" + i, preview: "미리보기" + i, text: "학습자: 안녕하세요\n호아랑: 네 안녕하세요 " + i,
});

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
    beforeParse(w) {
        w.localStorage.setItem("masamasaHistory", JSON.stringify(seed));
        w.localStorage.setItem("skipEntryGuide", "1");
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
        w.fetch = () => Promise.reject(new Error("no net"));
        w.scrollTo = () => {};
        w.Element.prototype.scrollIntoView = () => {};
    } });

setTimeout(() => {
    const d = dom.window.document;
    console.log("── 지난 대화 ──");
    d.getElementById("homeHistoryBtn").click();
    const ov = d.getElementById("histOverlay");
    ok("창이 열린다", !ov.classList.contains("hidden"));
    const items = d.querySelectorAll("#histList .hist-item");
    ok(`저장된 7개가 모두 보인다 (${items.length}개)`, items.length === 7);
    ok("각 항목이 기록을 품고 있다", !!items[0].querySelector(".hi-body"));

    const exp = d.getElementById("histExportBtn");
    ok("펼치기 전엔 내보내기 숨김", exp.classList.contains("hidden"));

    items[2].click();
    ok("누르면 그 항목이 펼쳐진다", items[2].classList.contains("open"));
    ok("목록은 그대로 남는다", !d.getElementById("histList").classList.contains("hidden"));
    ok("펼친 기록이 그 대화의 것", items[2].querySelector(".hi-body").textContent.includes("안녕하세요"));
    ok("내보내기가 나타난다", !exp.classList.contains("hidden"));

    items[5].click();
    ok("다른 것을 누르면 하나만 열린다", d.querySelectorAll(".hist-item.open").length === 1
        && items[5].classList.contains("open"));

    items[5].click();
    ok("다시 누르면 접힌다", !items[5].classList.contains("open"));
    ok("접으면 내보내기도 숨는다", exp.classList.contains("hidden"));

    console.log("── 홈 배경 영상 ──");
    ok("돌아올 때마다 다시 뽑는 함수", typeof dom.window.homeLoopReroll === "function");

    console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
    process.exit(fail ? 1 : 0);
}, 700);
