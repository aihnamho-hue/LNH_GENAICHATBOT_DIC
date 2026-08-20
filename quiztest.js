// ─────────────────────────────────────────────────────────────
// ② 추측에서 고른 뒤 **맞았는지 틀렸는지가 보이는가** (v139)
//   v138 까지 화면이 통째로 멎고 있었다 — classList.add("") 가 예외를 던져
//   forEach 가 끊기고 남은 선택지가 안 그려졌다. 문자열 검사로는 못 잡는다.
//   실제로 눌러 본다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const LESSON = JSON.parse(fs.readFileSync(process.argv[3] || "/tmp/w/lesson.json", "utf8"));
let bad = 0; const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u) => String(u).indexOf("/idc-lesson") >= 0
            ? Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LESSON) })
            : Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ drills: LESSON.drills }) });
        w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
        w.scrollTo = () => {};
        w.HTMLElement.prototype.scrollIntoView = () => {};
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
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
    /* ★ jsdom 의 el.click() 은 자리에 따라 **아무 일도 안 한다** (v140에서 겪음).
       손잡이는 멀쩡히 달려 있는데 이벤트가 아예 안 흘러서, 앱이 고장 난 것처럼 보인다.
       ordertest.js 때와 같은 함정의 뒷면이다 — 그때는 Node 쪽 MouseEvent 를 만들어
       jsdom 이 안 받았다. **창(window)의 MouseEvent** 로 만들면 진짜 눌림과 가장 가깝다. */
    const tap = (el) => el.dispatchEvent(
        new w.MouseEvent("click", { bubbles: true, cancelable: true }));
    try { await w.eval('idlOpen({key:"listen", easy:"듣고 있다고 알려 주기", acad:"상호작용적 듣기", emoji:"💬", gist:""})'); }
    catch (e) { ok("학습 창을 연다", false, e.message); }
    await new Promise((r) => setTimeout(r, 350));

    const opts = () => [...d.querySelectorAll(".idl-opt")];
    const res  = () => d.querySelector(".idl-res");
    const n = LESSON.quiz.n || 3;
    const ans = LESSON.quiz.ans;

    // ── ① 틀린 것을 눌렀을 때 ──
    console.log("\n── ① 틀린 것을 누른다");
    await w.eval("idl.picked=''; idl.step=2; idlPaint();");
    await new Promise((r) => setTimeout(r, 200));
    ok("고르기 전에 선택지가 다 있다", opts().length === n, opts().length + "/" + n);
    const wrongK = ["a", "b", "c"].slice(0, n).find((k) => k !== ans);
    const wi = ["a", "b", "c"].slice(0, n).indexOf(wrongK);
    tap(opts()[wi]);
    await new Promise((r) => setTimeout(r, 250));
    ok("선택지가 그대로 다 남아 있다", opts().length === n, opts().length + "/" + n);
    ok("정답 자리에 ok 가 붙었다",
       opts().some((o) => o.classList.contains("ok")),
       opts().map((o) => o.className).join(" | "));
    ok("내가 고른 자리에 no 가 붙었다", opts().some((o) => o.classList.contains("no")));
    ok("틀렸다는 줄이 보인다", !!res() && res().classList.contains("no"),
       res() ? res().textContent : "(없음)");
    ok("틀렸을 때 힌트가 들어 있다", !!res() && res().textContent.replace(/\s/g, "").length > 3);
    ok("아직 다음으로 못 넘어간다", d.getElementById("idlNext").disabled);

    // ★ v140 — 1초 뒤 **저절로** 첫 화면으로. 단추를 또 누르게 하면 거기서 그만둔다.
    console.log("\n── ①-2 1초 뒤 저절로 되돌아가는가");
    await new Promise((r) => setTimeout(r, 1300));
    ok("선택지가 다시 눌린다", opts().length === n && !opts()[0].disabled,
       opts().map((o) => o.className + (o.disabled ? "(잠김)" : "")).join(" | "));
    ok("색 표시가 지워졌다", opts().every((o) => !o.classList.contains("ok") && !o.classList.contains("no")));
    ok("결과 줄이 사라졌다", !res());
    ok("짚어 준 말은 곁에 남았다", !!d.querySelector("#idlBody .idl-miss"),
       (d.querySelector("#idlBody .idl-miss") || {}).textContent);
    // 몇 번이든 — 두 번째로 틀려도 다시 돌아온다
    tap(opts()[wi]);
    await new Promise((r) => setTimeout(r, 1300));
    ok("두 번째로 틀려도 또 돌아온다", opts().length === n && !opts()[0].disabled);

    // ── ② 맞는 것을 눌렀을 때 ──
    // ★ 상태를 손으로 주무르지 않는다 — 사람이 하듯 **이어서** 맞는 것을 누른다.
    //   (틀린 뒤 저절로 돌아온 화면에서 그대로 다시 고르는 것이 실제 흐름이다)
    console.log("\n── ② 되돌아온 화면에서 맞는 것을 누른다");
    const ai = ["a", "b", "c"].slice(0, n).indexOf(ans);
    tap(opts()[ai]);
    await new Promise((r) => setTimeout(r, 250));
    ok("선택지가 그대로 다 남아 있다", opts().length === n, opts().length + "/" + n);
    ok("맞았다는 줄이 보인다", !!res() && res().classList.contains("ok"),
       res() ? res().textContent : "(없음)");
    ok("🎉 가 보인다", !!res() && res().textContent.indexOf("🎉") >= 0);
    ok("다음으로 넘어갈 수 있다", !d.getElementById("idlNext").disabled);

    // ── ③ 그리다 터진 곳 ──
    console.log("\n── ③ 시작 영상이 진짜 눌림을 삼키지 않는가");
    // 손가락으로 건너뛸 때만 삼켜야 한다. 시간 초과로 걷힐 때 삼키면
    // 그 뒤 0.8초 안에 누른 것이 통째로 사라진다.
    ok("건너뛸 때만 삼킨다", /if \(byTap === true\) swallowNextClick\(\)/.test(html));
    ok("손가락 쪽만 byTap 을 준다", /pointerdown", \(\) => endSplash\(true\)/.test(html));
    ok("시간 초과 쪽은 안 준다", !/setTimeout\(\(\) => endSplash\(true\)/.test(html));

    console.log("\n── ④ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 채점 화면 이상 없음");
    process.exit(bad ? 1 : 0);
}, 700);
