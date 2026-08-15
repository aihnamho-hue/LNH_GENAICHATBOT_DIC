/* v93 — PC 배치 · 자유 대화 세 장 · 종료 반응 · 별점 기록 */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

function boot(width, done) {
    const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
        beforeParse(w) {
            w.localStorage.setItem("skipEntryGuide", "1");
            Object.defineProperty(w, "innerWidth", { value: width, configurable: true });
            w.matchMedia = (q) => ({ matches: /min-width: 821px/.test(q) ? width >= 821 : false,
                media: q, addEventListener() {}, addListener() {}, removeEventListener() {} });
            w.HTMLMediaElement.prototype.play = () => Promise.resolve();
            w.HTMLMediaElement.prototype.pause = () => {};
            w.fetch = () => Promise.reject(new Error("no net"));
            w.Element.prototype.scrollIntoView = () => {};
        } });
    setTimeout(() => done(dom.window.document, dom.window, dom), 700);
}

console.log("── ② PC 에서 도움말이 왼쪽 기둥으로 ──");
boot(1400, (d, w, dom1) => {
    const dock = d.getElementById("scfDock");
    ok("대화 종료하기 아래(왼쪽 패널)로 옮겨진다", dock.parentElement.id === "scfSideSlot");
    ok("왼쪽용 모양(side)이 붙는다", dock.classList.contains("side"));
    ok("왼쪽 자리는 캐릭터 패널 안", d.getElementById("scfSideSlot").closest(".character-panel") !== null);
    ok("말차례가 바뀌면 다시 받아 온다", /scfAutoTimer[\s\S]{0,300}?requestScaffold\(\)/.test(html));
    dom1.window.close();

    console.log("── 휴대폰에서는 그대로 ──");
    boot(420, (d2, w2, dom2) => {
        const dock2 = d2.getElementById("scfDock");
        ok("대화창 아래 원래 자리", dock2.parentElement.id === "scfHomeSlot");
        ok("side 모양은 안 붙는다", !dock2.classList.contains("side"));
        dom2.window.close();

        console.log("── ① 자유 대화 결과 세 장 ──");
        boot(420, (d3, w3, dom3) => {
            const vis = (id) => w3.getComputedStyle(d3.getElementById(id)).display !== "none";
            d3.getElementById("freeFbOverlay").classList.remove("hidden");
            w3.eval("freeGo(0)");
            ok("① 자기 성찰 — 별 다섯", d3.querySelectorAll("#freePage0 .self-star").length === 5);
            ok("첫 장엔 '이전'이 없고 '다음'이 한 줄", !vis("freePrevBtn")
               && d3.getElementById("freeNextBtn").classList.contains("wide"));
            d3.getElementById("freeNextBtn").click();
            ok("② 상호작용 대화 능력", !d3.getElementById("freePage1").classList.contains("hidden")
               && !!d3.querySelector("#freePage1 #freeIdcList"));
            d3.getElementById("freeNextBtn").click();
            ok("③ 총평", !d3.getElementById("freePage2").classList.contains("hidden")
               && !!d3.querySelector("#freePage2 #freeReviewEl"));
            ok("마지막 장은 '다음' 없이 '홈으로'", !vis("freeNextBtn") && vis("freeFbCloseBtn"));
            d3.getElementById("freePrevBtn").click();
            ok("← 되돌아온다", !d3.getElementById("freePage1").classList.contains("hidden"));
            ok("점은 세 개", d3.querySelectorAll("#freeDots .res-dot").length === 3);

            console.log("── ④ 별점을 기록에 남긴다 ──");
            ok("기록 머리말에 별점이 들어간다", /스스로 매긴 별점/.test(html));
            ok("이미 저장된 기록도 고쳐 준다", /list\[0\]\.stats\.selfRating = v/.test(html));
            ok("서버에도 보낸다", /type: "self_rating", value: v/.test(html));
            const stars = d3.querySelectorAll("#freePage0 .self-star");
            w3.eval("freeGo(0)");
            stars[4].click();
            ok("별 다섯을 누르면 다섯 칸이 찬다", d3.querySelectorAll("#freePage0 .self-star.on").length === 5);

            console.log("── ③ 종료를 누르면 곧바로 반응 ──");
            ok("문을 먼저 닫는다", /closeDoorNow\(t\("doorEnd"\)\)/.test(html));
            ok("문이 닫힌 만큼만 더 기다린다", /function doorSwap/.test(html)
               && /1350 - \(Date\.now\(\) - doorClosedAt\)/.test(html));
            ok("웹소켓은 끊지 않는다(총평이 와야 하므로)",
               /stopSession\(\) 을 부르면 웹소켓까지 닫혀/.test(html));

            console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
            process.exit(fail ? 1 : 0);
        });
    });
});
