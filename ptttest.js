// ─────────────────────────────────────────────────────────────
// 꾹 눌러 말하기가 **세 자리에서 같은가** (v139)
//   ㄱ) 주제·자유 대화(#pttBtn)  ㄴ) 발화 연습(#prMicBtn)  ㄷ) 학습 ⑤걸음
//   셋이 저마다 다르면 학습자가 자리를 옮길 때마다 다시 익혀야 한다.
//   ★ 원본을 베끼지 않는다 — 페이지를 실제로 돌려 단추를 만들어 본다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const LESSON = JSON.parse(fs.readFileSync(process.argv[3] || "/tmp/w/lesson.json", "utf8"));
let bad = 0; const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const buzzes = [];
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
        // 진동을 가로채 **정말 부르는지** 본다 (기기에 없어도 코드는 불러야 한다)
        w.navigator.vibrate = (p) => { buzzes.push(p); return true; };
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
    try { w.eval('uiLang="ko"'); } catch (e) {}

    console.log("── ① 손맛을 한 곳에서 만드는가");
    const hasBuzz = (() => { try { return typeof w.eval("pttBuzz") === "function"; } catch (e) { return false; } })();
    ok("pttBuzz 가 있다", hasBuzz);
    if (hasBuzz) {
        buzzes.length = 0;
        w.eval('pttBuzz("start"); pttBuzz("stop");');
        ok("진동을 정말 부른다", buzzes.length === 2, JSON.stringify(buzzes));
        ok("누를 때가 뗄 때보다 길다", buzzes[0] > buzzes[1], JSON.stringify(buzzes));
    }

    console.log("\n── ② 세 자리가 같은 말을 쓰는가");
    const T  = (k) => { try { return w.eval(`t(${JSON.stringify(k)})`); } catch (e) { return ""; } };
    const IT = (k) => { try { return w.eval(`idcT(${JSON.stringify(k)})`); } catch (e) { return ""; } };
    ok("누르기 전 글씨가 같다", T("pttHold") === IT("hold"), `${T("pttHold")} / ${IT("hold")}`);
    ok("말하는 중 글씨가 같다", T("pttTalking") === IT("talking"), `${T("pttTalking")} / ${IT("talking")}`);
    ok("아래 안내가 같다", T("prMicRec") === IT("micRec"), `${T("prMicRec")} / ${IT("micRec")}`);
    ok("알아듣는 중 글씨가 같다", T("prStt") === IT("checking"), `${T("prStt")} / ${IT("checking")}`);

    console.log("\n── ③ 세 자리가 같은 옷을 입는가");
    const main = d.getElementById("pttBtn");
    const pr   = d.getElementById("prMicBtn");
    ok("주제·자유 대화 단추가 있다", !!main, main && main.className);
    ok("발화 연습 단추가 있다", !!pr, pr && pr.className);
    // 학습 ⑤ 걸음을 실제로 그려 본다
    try { await w.eval('idlOpen({key:"topic", easy:"이야기 이끌기", acad:"주제 관리", emoji:"💬", gist:""})'); }
    catch (e) { ok("학습 창을 연다", false, e.message); }
    await new Promise((r) => setTimeout(r, 400));
    await w.eval("idl.step=5; idlPaint();");
    await new Promise((r) => setTimeout(r, 450));
    const idlMic = d.querySelector("#idlBody .pr-mic");
    ok("학습 ⑤ 도 발화 연습과 같은 옷(.pr-mic)", !!idlMic,
       (d.querySelector("#idlBody button") || {}).className);
    ok("학습 ⑤ 에 아래 안내 자리가 있다", !!d.querySelector("#idlBody .pr-mic-label"));
    ok("학습 ⑤ 글씨가 발화 연습과 같다",
       !!idlMic && idlMic.textContent.trim() === T("pttHold").trim(),
       idlMic ? idlMic.textContent : "");

    console.log("\n── ④ 학습 ⑤ 는 발화 연습과 같은 뼈대인가");
    ok("왼쪽 정렬 안내 한 줄", !!d.querySelector("#idlBody .pr-step"));
    ok("내가 할 말이 큰 카드로", !!d.querySelector("#idlBody .pr-target"));
    ok("다시 듣기 단추", !!d.querySelector("#idlBody .pr-listen-btn"));
    ok("대화문을 안 보인다", d.querySelectorAll("#idlBody .idl-line").length === 0);
    ok("해설을 안 보인다", d.querySelectorAll("#idlBody .idl-say").length === 0);

    console.log("\n── ⑤ 글자가 끌려 선택되지 않는가");
    const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
    ok("html·body 에 user-select:none", /html,\s*body\s*\{[^}]*user-select:\s*none/.test(css));
    ok("길게 눌러도 메뉴가 안 뜬다", /-webkit-touch-callout:\s*none/.test(css));
    ok("입력칸은 다시 열어 준다", /input,\s*textarea[^}]*user-select:\s*text/.test(css));

    console.log("\n── ⑥ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 말하기 단추 이상 없음");
    process.exit(bad ? 1 : 0);
}, 700);
