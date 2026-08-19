// ─────────────────────────────────────────────────────────────
// 차례 맞히기가 실제로 눌리는가 (v136)
//   「기능 단계의 조직」만 물음 꼴이 다르다 — 조각을 순서대로 쌓는다.
//   화면을 진짜 돌려서 **눌러 본다.** 문자열 검사로는 못 잡는다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const LESSON = JSON.parse(fs.readFileSync(process.argv[3] || "/tmp/w/lesson_stage.json", "utf8"));
let bad = 0; const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u) => String(u).indexOf("/idc-lesson") >= 0
            ? Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LESSON) })
            : Promise.resolve({ ok: false, status: 0, json: () => Promise.resolve({}) });
        w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
        w.scrollTo = () => {}; w.HTMLElement.prototype.scrollIntoView = () => {};
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.load = () => {};
        // jsdom 은 pause 를 안 만들어 둔다 — 없는 것을 오류로 세면 검사가 거짓말을 한다
        w.HTMLMediaElement.prototype.pause = () => {};
    },
});
const w = dom.window;
// ★ el.click() 을 쓴다.
//   new MouseEvent(...) 를 dispatchEvent 로 쏘면 jsdom 이 자리에 따라 안 받는 때가 있다.
//   그러면 **앱이 멀쩡한데 검사만 빨개진다** — 실제로 한 번 속았다.
const click = (el) => el.click();

setTimeout(async () => {
    const d = w.document;
    const q = LESSON.quiz;
    console.log("── ① 차례 맞히기 화면이 그려지는가");
    try { await w.eval('idlOpen({key:"stage", easy:"대화의 흐름 짜기", acad:"기능 단계의 조직과 흐름", emoji:"", gist:""})'); }
    catch (e) { ok("idlOpen", false, e.message); }
    await new Promise((r) => setTimeout(r, 400));
    const step = async (n) => { try { await w.eval(`idl.step = ${n}; idlPaint();`); } catch (e) { errs.push(e.message); }
                                await new Promise((r) => setTimeout(r, 200)); };
    await step(2);
    let tray = [...d.querySelectorAll(".idl-tray .idl-chip")];
    ok("조각이 다 나왔다", tray.length === q.n, `${tray.length} / ${q.n}`);
    ok("조각 이름이 채워졌다", tray.every((b) => b.textContent.trim()), tray.map((b) => b.textContent.trim()).join("|"));
    ok("아직 쌓인 것이 없다", d.querySelectorAll(".idl-stack .idl-chip.put").length === 0);
    ok("맞히기 전에는 다음으로 못 간다", d.getElementById("idlNext").disabled);

    console.log("\n── ② 틀린 차례로 눌러 본다");
    const nameOf = (i) => (q.chips.find((c) => c.i === i) || {}).name;
    const wrong = q.order.slice().reverse();            // 거꾸로 = 확실히 틀림
    for (const i of wrong) {
        const b = [...d.querySelectorAll(".idl-tray .idl-chip")].find((x) => x.querySelector("span").textContent === nameOf(i));
        if (b) click(b); await new Promise((r) => setTimeout(r, 60));
    }
    ok("다 쌓으면 채점된다", d.querySelectorAll(".idl-stack .idl-chip.put").length === q.n);
    ok("틀린 자리에 표가 난다", d.querySelectorAll(".idl-chip.put.no").length > 0);
    ok("틀리면 못 넘어간다", d.getElementById("idlNext").disabled);
    const again = [...d.querySelectorAll(".idl-btn")].find((b) => b.style.width === "100%");
    ok("다시 하기 단추가 있다", !!again);

    console.log("\n── ③ 맞는 차례로 눌러 본다");
    if (again) { click(again); await new Promise((r) => setTimeout(r, 200)); }
    ok("다시 하면 판이 비워진다", d.querySelectorAll(".idl-stack .idl-chip.put").length === 0);
    for (const i of q.order) {
        const b = [...d.querySelectorAll(".idl-tray .idl-chip")].find((x) => x.querySelector("span").textContent === nameOf(i));
        if (b) click(b); await new Promise((r) => setTimeout(r, 60));
    }
    ok("다 맞으면 초록으로", d.querySelectorAll(".idl-chip.put.ok").length === q.n,
       `${d.querySelectorAll(".idl-chip.put.ok").length} / ${q.n}`);
    ok("맞히면 다음으로 갈 수 있다", !d.getElementById("idlNext").disabled);
    await new Promise((r) => setTimeout(r, 1600));
    ok("맞히면 ③ 뜻풀이로 넘어간다", w.eval("idl.step") === 3, w.eval("idl.step"));

    console.log("\n── ④ 쌓다가 빼기");
    // ★ ③에서 이미 맞혀 ③걸음으로 넘어간 뒤다. 판을 비우고 ②로 되돌린 다음
    //   **다시 그려질 때까지 기다린다.** 안 기다리면 조각이 아직 없어 null 을 누른다.
    // ★ idl.ord 를 **새 배열로 갈아 끼우면** 안 된다.
    //   idlPaint 가 그린 단추는 그릴 당시의 q·idl 을 붙들고 있는데,
    //   step 을 3으로 넘긴 뒤에 남은 예약(1.4초)이 나중에 다시 그리면서
    //   내 손이 쥔 단추와 화면의 단추가 어긋난다.
    //   그래서 **비우기만 하고**(length=0) 예약이 다 지나가길 기다린 뒤 그린다.
    await new Promise((r) => setTimeout(r, 1600));       // 남은 예약이 지나가길
    w.eval("idl.ord.length = 0; idl.step = 2; idlPaint();");
    let one = null;
    for (let i = 0; i < 20 && !one; i++) {
        await new Promise((r) => setTimeout(r, 60));
        one = d.querySelector(".idl-tray .idl-chip");
    }
    ok("판을 비우면 조각이 다시 나온다", !!one);
    if (!one) { console.log("\n💥 조각이 안 나와 더 못 본다"); process.exit(1); }
    click(one); await new Promise((r) => setTimeout(r, 150));
    const put1 = d.querySelector(".idl-stack .idl-chip.put");
    ok("하나 쌓였다", !!put1 && d.querySelectorAll(".idl-stack .idl-chip.put").length === 1);
    // ★ 앞이 실패하면 여기서 멈춘다. 안 그러면 null 을 눌러 터지고,
    //   **진짜 실패 하나가 예외로 덮여** 뒤 항목이 통째로 안 돈다.
    if (!put1) { console.log("\n💥 안 쌓여서 더 못 본다"); process.exit(1); }
    click(put1); await new Promise((r) => setTimeout(r, 120));
    ok("쌓은 것을 눌러 도로 뺀다", d.querySelectorAll(".idl-stack .idl-chip.put").length === 0);
    ok("뺀 조각이 아래로 돌아온다", d.querySelectorAll(".idl-tray .idl-chip").length === q.n);

    console.log("\n── ⑤ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));
    console.log("\n" + (bad ? `💥 ${bad}건` : "🎉 차례 맞히기 이상 없음"));
    process.exit(bad ? 1 : 0);
}, 1400);
