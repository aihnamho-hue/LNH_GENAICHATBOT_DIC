// ─────────────────────────────────────────────────────────────
// 화면이 「본 편」을 제대로 적어 보내는가 (v140)
//   v139 까지 place(자리 설명)를 보냈는데 서버는 id 로 견줬다.
//   단위가 어긋나 한 번도 안 맞았고, 그래서 한 편만 계속 나왔다.
//   ★ 페이지를 실제로 돌려 학습 창을 여섯 번 열어 본다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const CORPUS = JSON.parse(fs.readFileSync("idc_corpus/topic.json", "utf8"));
const BASE = JSON.parse(fs.readFileSync("/tmp/w/lesson.json", "utf8"));
let bad = 0; const errs = [], asked = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const IDS = CORPUS.items.map((x) => x.id);          // topic-1 … topic-5
let turn = 0;

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u, o) => {
            const s = String(u);
            if (s.indexOf("/idc-lesson") >= 0) {
                let b = {};
                try { b = JSON.parse((o && o.body) || "{}"); } catch (e) {}
                asked.push(b);                        // 화면이 무엇을 보냈나
                // 서버 흉내는 최소로 — 차례대로 하나씩 내준다.
                // (고르는 규칙 자체는 rotatetest.py 가 main.py 를 돌려서 본다)
                const id = IDS[turn % IDS.length]; turn += 1;
                return Promise.resolve({ ok: true, status: 200,
                    json: () => Promise.resolve(Object.assign({}, BASE,
                        { id, place: "자리-" + id, pool: IDS.length })) });
            }
            return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ drills: BASE.drills }) });
        };
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
    try { w.eval('uiLang="ko"'); } catch (e) {}
    const open = async () => {
        await w.eval('idlOpen({key:"topic", easy:"이야기 이끌기", acad:"주제 관리", emoji:"💬", gist:""})');
        await new Promise((r) => setTimeout(r, 260));
        try { await w.eval("idlClose()"); } catch (e) {}
        await new Promise((r) => setTimeout(r, 60));
    };

    console.log("── ① 여섯 번 열어 본다");
    for (let i = 0; i < 6; i++) await open();
    ok("여섯 번 다 물어봤다", asked.length === 6, asked.length);

    console.log("\n── ② 보낸 것이 편 id 인가 (자리 설명이 아니라)");
    const last = asked[asked.length - 1];
    ok("seen 이 편 id 다", (last.seen || []).every((x) => IDS.indexOf(x) >= 0),
       JSON.stringify(last.seen));
    ok("seen 에 자리 설명이 안 섞였다", !(last.seen || []).some((x) => String(x).indexOf("자리-") === 0),
       JSON.stringify(last.seen));
    ok("자리 설명은 avoid 로 따로 갔다", (last.avoid || []).some((x) => String(x).indexOf("자리-") === 0),
       JSON.stringify(last.avoid));

    console.log("\n── ③ 본 것이 쌓이는가");
    const lens = asked.map((a) => (a.seen || []).length);
    ok("처음엔 비어 있다", lens[0] === 0, JSON.stringify(lens));
    ok("열 때마다 쌓인다", lens[1] === 1 && lens[2] === 2, JSON.stringify(lens));
    ok(`편 수보다 하나 적게만 쥔다 (${IDS.length - 1}개)`,
       Math.max(...lens) === IDS.length - 1, JSON.stringify(lens));
    ok("받은 것을 그대로 적었다",
       JSON.stringify(asked[3].seen) === JSON.stringify(IDS.slice(0, 3)),
       JSON.stringify(asked[3].seen));

    console.log("\n── ④ 새로 고쳐도 남는가");
    let saved = null;
    try { saved = JSON.parse(w.localStorage.getItem("idlSeen2") || "null"); } catch (e) {}
    ok("기기에 적어 두었다", !!saved && Array.isArray(saved.topic), JSON.stringify(saved));
    ok("요소마다 따로 적는다", !!saved && Object.keys(saved).length === 1 && saved.topic,
       JSON.stringify(saved && Object.keys(saved)));

    console.log("\n── ⑤ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 본 편 적어 두기 이상 없음");
    process.exit(bad ? 1 : 0);
}, 700);
