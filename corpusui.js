// ─────────────────────────────────────────────────────────────
// 검수한 대화문이 **화면까지** 닿는가 (v135)
//   서버가 잘 골라도 화면이 못 그리면 소용없다. cardtest.js 와 같은 방식으로
//   페이지를 실제로 돌리고, /idc-lesson 응답을 검수본으로 가로채 먹인다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const LESSON = JSON.parse(fs.readFileSync(process.argv[3] || "/tmp/w/lesson.json", "utf8"));
let bad = 0, drillId = null;
const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/",
    virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u, o) => {
            const s = String(u);
            if (s.indexOf("/idc-lesson") >= 0)
                return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LESSON) });
            if (s.indexOf("/idc-drill") >= 0) {
                try { drillId = JSON.parse((o && o.body) || "{}").id; } catch (e) {}
                return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ drills: LESSON.drills }) });
            }
            return Promise.resolve({ ok: false, status: 0, json: () => Promise.resolve({}) });
        };
        w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
        w.scrollTo = () => {};
        w.HTMLElement.prototype.scrollIntoView = () => {};
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.load = () => {};
        w.AudioContext = w.webkitAudioContext = function () {
            const g = { gain: { value: 0, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime() {} }, connect: (x) => x, disconnect() {} };
            return { state: "running", currentTime: 0, destination: {}, createGain: () => g,
                     createMediaElementSource: () => g, createMediaStreamSource: () => g,
                     createAnalyser: () => Object.assign({}, g, { fftSize: 512, getFloatTimeDomainData() {} }),
                     resume: () => Promise.resolve(), close: () => Promise.resolve() };
        };
    },
});
const w = dom.window;

setTimeout(async () => {
    const d = w.document;
    console.log("── ① 학습 창이 검수본으로 그려지는가");
    try { await w.eval('idlOpen(IDC_ELS ? IDC_ELS[0] : {key:"context"})'); }
    catch (e) { /* 요소 객체 이름이 다르면 아래에서 다시 */ }
    await new Promise((r) => setTimeout(r, 300));
    let body = d.querySelector(".idl-body, #idlBody");
    if (!body || !body.textContent.trim()) {
        try { await w.eval('idlOpen({key:"context", easy:"상대에 맞춰 말하기", acad:"맥락·정체성 인식", emoji:"", gist:""})'); }
        catch (e) { ok("idlOpen 을 부를 수 있다", false, e.message); }
        await new Promise((r) => setTimeout(r, 400));
        body = d.querySelector(".idl-body, #idlBody");
    }
    ok("학습 창이 떴다", !!(body && body.textContent.trim()));
    const t = () => (body ? body.textContent.replace(/\s+/g, " ") : "");
    // ★ 걸음마다 보이는 것이 다르다 — ⓪들어가기 ①듣기 ②추측 ③뜻풀이 ④문형 ⑤사용.
    //   한 화면만 보고 「대화문이 없다」고 하면 검사가 거짓말을 한다(처음에 그랬다).
    const step = async (n) => {
        try { await w.eval(`idl.step = ${n}; idlPaint();`); } catch (e) { errs.push("step" + n + ": " + e.message); }
        await new Promise((r) => setTimeout(r, 250));
        body = d.querySelector(".idl-body, #idlBody");
    };
    ok("⓪ 자리 안내가 보인다", t().indexOf(LESSON.place.slice(0, 10)) >= 0, t().slice(0, 60));
    await step(1);
    const first = LESSON.script[0].text.slice(0, 10);
    ok("① 대화문이 보인다", t().indexOf(first) >= 0, first);
    const mk = LESSON.script[LESSON.mark].text.slice(0, 10);
    ok("① 표시할 줄도 보인다", t().indexOf(mk) >= 0, mk);

    console.log("\n── ② 물음 세 갈래");
    await step(2);
    const opts = [...d.querySelectorAll(".idl-opt, .idl-body button")].map((b) => b.textContent.trim()).filter(Boolean);
    const q = LESSON.quiz;
    ["a", "b", "c"].forEach((k) => {
        ok(`선택지 ${k}`, opts.some((o) => o.indexOf(q[k].slice(0, 12)) >= 0), q[k].slice(0, 20));
    });
    ok("물음이 보인다", t().indexOf(q.q.slice(0, 12)) >= 0, q.q.slice(0, 24));

    console.log("\n── ③ 뜻풀이·문형이 검수본 것인가");
    await step(3);
    ok("③ 뜻풀이가 보인다", t().indexOf(LESSON.meaning[0].ko.slice(0, 12)) >= 0);
    await step(4);
    // ★ v138 — 문형은 「~」인 채로가 아니라 **그 대화문의 말로 채워져** 보인다.
    //   「나도 ~한 적 있어」가 아니라 「나도 등산한 적 있어」.
    //   붉은색(core) = 그대로 외울 뼈대 · 검은색(slot) = 갈아 끼우는 자리
    const fms = [...d.querySelectorAll(".idl-form .fm")].map(
        (f) => [...f.querySelectorAll("span")].map(
            (s) => ({ c: s.className, t: s.textContent })));
    ok("④ 문형이 몇 줄 떴다", fms.length >= LESSON.forms.length, fms.length + "/" + LESSON.forms.length);
    const shown = fms.map((p) => p.map((x) => x.t).join(""));
    ok("④ 화면에 「~」가 안 남았다", shown.every((s) => s.indexOf("~") < 0), shown.join(" / "));
    (LESSON.forms_filled || []).forEach((p, i) => {
        const want = p.map((x) => x[0]).join("");
        ok(`④ 「${LESSON.forms[i]}」 → 「${want}」`, shown.indexOf(want) >= 0, shown.join(" / "));
    });
    // 채울 것이 있던 문형은 검은 칸이 실제로 갈려 있어야 한다
    const hadSlot = (LESSON.forms || []).some((f) => f.indexOf("~") >= 0);
    ok("④ 갈아 끼우는 자리가 검게 갈렸다",
       !hadSlot || fms.some((p) => p.some((x) => x.c === "slot")),
       fms.map((p) => p.map((x) => x.c[0] + x.t).join("|")).join(" / "));
    ok("④ 외울 뼈대가 붉게 갈렸다", fms.every((p) => p.some((x) => x.c === "core")));

    console.log("\n── ④ id 가 ⑤연습까지 흘러가는가");
    ok("응답에 id 가 있다", !!LESSON.id, LESSON.id);
    await step(5);
    await new Promise((r) => setTimeout(r, 300));
    ok("/idc-drill 로 id 를 보냈다", drillId === LESSON.id, `보낸 값: ${JSON.stringify(drillId)}`);

    console.log("\n── ⑤ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log("\n" + (bad ? `💥 ${bad}건` : "🎉 화면까지 닿는다"));
    process.exit(bad ? 1 : 0);
}, 1400);
