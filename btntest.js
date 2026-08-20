/* v92 — 결과 화면 단추가 쪽마다 제대로 숨고 나오는가 */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
    beforeParse(w) {
        w.localStorage.setItem("skipEntryGuide", "1");
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
        w.fetch = () => Promise.reject(new Error("no net"));
        w.Element.prototype.scrollIntoView = () => {};
    } });

setTimeout(() => {
    const d = dom.window.document, w = dom.window;
    const vis = (id) => w.getComputedStyle(d.getElementById(id)).display !== "none";
    console.log("── .hidden 이 단추에도 먹는가 ──");
    ["rpCloseBtn", "resPrevBtn", "resNextBtn", "histExportBtn", "freeFbCloseBtn"].forEach(id => {
        const el = d.getElementById(id);
        el.classList.add("hidden");
        ok(`${id} 가 .hidden 으로 숨는다`, w.getComputedStyle(el).display === "none");
        el.classList.remove("hidden");
    });

    console.log("── 쪽마다 보이는 단추 ──");
    d.getElementById("rpResultOverlay").classList.remove("hidden");
    // v141 — 별점과 AI 판정 사이에 「요소 자가 점검」과 「후기」가 들어왔다
    const want = [
        [0, { prev: false, next: true,  home: false }, "자기 성찰(별점)"],
        [1, { prev: true,  next: true,  home: false }, "요소 자가 점검"],
        [2, { prev: true,  next: true,  home: false }, "후기"],
        [3, { prev: true,  next: true,  home: false }, "대화 흐름"],
        [4, { prev: true,  next: true,  home: false }, "상호작용 능력"],
        [5, { prev: true,  next: false, home: true  }, "총평(마지막)"],
    ];
    want.forEach(([p, exp, name]) => {
        w.eval(`resGo(${p})`);
        const got = { prev: vis("resPrevBtn"), next: vis("resNextBtn"), home: vis("rpCloseBtn") };
        const okAll = got.prev === exp.prev && got.next === exp.next && got.home === exp.home;
        ok(`${p}쪽 ${name} — 이전 ${got.prev ? "○" : "×"} / 다음 ${got.next ? "○" : "×"} / 홈으로 ${got.home ? "○" : "×"}`, okAll);
    });
    console.log("── 마지막 쪽 ──");
    w.eval("resGo(5)");
    ok("더 갈 데가 없으니 '다음'이 없다", !vis("resNextBtn"));
    ok("대신 '홈으로'가 나온다", vis("rpCloseBtn"));
    ok("첫 쪽의 '다음'은 한 줄을 다 쓴다",
       (w.eval("resGo(0)"), d.getElementById("resNextBtn").classList.contains("wide")));
    ok("가운데 쪽에선 두 칸으로 나뉜다",
       (w.eval("resGo(1)"), !d.getElementById("resNextBtn").classList.contains("wide")));
    ok("이전·다음이 한 줄 두 칸", /\.res-actions \{[^}]*grid-template-columns: 1fr 1fr/.test(html));

    console.log("── 늦게 온 결과도 채워 넣는가 ──");
    ok("도착이 늦어도 다시 그린다", /기다리다 지쳐 먼저 화면을 띄운 뒤에 결과가 왔다면/.test(html));
    ok("결과는 13초 안에 띄운다(총평은 뒤따라 온다)",
   /concludeRoleplay, 13000/.test(html) && /concludeFree, 13000/.test(html));

    console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
    process.exit(fail ? 1 : 0);
}, 800);
