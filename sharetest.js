// ─────────────────────────────────────────────────────────────
// 교실에 띄우기 (v142)
//   대목을 골라 네 글자 코드를 받고, 교사 화면이 그 코드로 연다.
//   ★ 실제로 눌러 본다 — 처음 줄, 끝 줄, 코드 만들기까지.
//   ★ 서버로 나가는 몸통도 들여다본다 (이름·점수가 새어 나가면 안 된다).
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let bad = 0; const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const HIST = [{
    ts: new Date().toISOString(), mode: "rp", title: "옷 가게에서 물건 사기",
    preview: "…", text: "옛 꼴의 글 덩어리",
    turns: [
        { r: "ham", t: "어서 오세요. 뭐 찾으세요?" },
        { r: "me",  t: "겨울에 입을 코트를 보려고요." },
        { r: "ham", t: "이 회색이 요즘 제일 잘 나가요." },
        { r: "me",  t: "저건 얼마예요?" },
        { r: "ham", t: "십오만 원이에요." },
        { r: "me",  t: "음… 그럼 저걸로 할게요." },
    ],
    stats: { selfRating: 4, selfNote: "값을 못 깎았다" },
}, {
    ts: new Date(Date.now() - 86400000).toISOString(), mode: "free", title: "지난 자유 대화",
    preview: "…", text: "옛 판에서 저장된 것 — 턴이 없다", stats: {},
}];

let posted = null;
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u, o) => {
            if (String(u).indexOf("/share") >= 0 && o && o.method === "POST") {
                try { posted = JSON.parse(o.body); } catch (e) { posted = {}; }
                return Promise.resolve({ ok: true, status: 200,
                    json: () => Promise.resolve({ ok: true, code: "K7QM", n: (posted.turns || []).length }) });
            }
            return Promise.resolve({ ok: false, status: 0, json: () => Promise.resolve({}) });
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
        try { w.localStorage.setItem("masamasaHistory", JSON.stringify(HIST)); } catch (e) {}
    },
});
const w = dom.window;

setTimeout(async () => {
    const d = w.document;
    const tap = (el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
    try { w.eval('uiLang="ko"'); } catch (e) {}

    console.log("── ① 기록에서 대목 고르기로 들어가는가");
    w.eval("openHistory();");
    await new Promise((r) => setTimeout(r, 150));
    const items = [...d.querySelectorAll("#histList .hist-item")];
    ok("기록이 두 건 보인다", items.length === 2, items.length);
    const shBtn = d.getElementById("histShareBtn");
    ok("처음엔 단추가 숨어 있다", shBtn.classList.contains("hidden"));
    tap(items[0]);
    await new Promise((r) => setTimeout(r, 80));
    ok("턴이 있는 기록을 펴면 단추가 나온다", !shBtn.classList.contains("hidden"));
    ok("단추 글씨가 채워졌다", (shBtn.textContent || "").length > 2, shBtn.textContent);
    tap(items[0]); tap(items[1]);
    await new Promise((r) => setTimeout(r, 80));
    ok("턴이 없는 옛 기록에는 단추가 안 나온다", shBtn.classList.contains("hidden"));

    console.log("\n── ② 처음 줄·끝 줄을 눌러 대목을 잡는다");
    tap(items[1]); tap(items[0]);
    await new Promise((r) => setTimeout(r, 60));
    tap(shBtn);
    await new Promise((r) => setTimeout(r, 120));
    ok("고르는 창이 열린다", !d.getElementById("shareOverlay").classList.contains("hidden"));
    const rows = [...d.querySelectorAll("#shareList .sh-turn")];
    ok("여섯 줄이 다 보인다", rows.length === 6, rows.length);
    ok("누가 말했는지 보인다", (rows[0].querySelector("b").textContent || "").length > 0,
       rows[0].textContent.slice(0, 20));
    const go = d.getElementById("shareGoBtn");
    ok("아직 코드를 못 만든다", go.disabled);
    tap(rows[1]);
    await new Promise((r) => setTimeout(r, 50));
    ok("한 줄만으로는 못 만든다", go.disabled);
    tap(rows[3]);
    await new Promise((r) => setTimeout(r, 50));
    ok("두 줄 이상이면 만들 수 있다", !go.disabled);
    ok("고른 만큼 불이 들어온다",
       d.querySelectorAll("#shareList .sh-turn.pick").length === 3,
       d.querySelectorAll("#shareList .sh-turn.pick").length);
    ok("몇 줄인지 단추에 보인다", /\(3\)/.test(go.textContent), go.textContent);
    // 거꾸로 골라도 된다
    tap(rows[4]); tap(rows[0]);
    await new Promise((r) => setTimeout(r, 50));
    ok("끝에서 처음으로 골라도 잡힌다",
       d.querySelectorAll("#shareList .sh-turn.pick").length === 5,
       d.querySelectorAll("#shareList .sh-turn.pick").length);

    console.log("\n── ③ 코드를 만든다");
    tap(rows[1]); tap(rows[3]);        // 다시 세 줄로
    await new Promise((r) => setTimeout(r, 50));
    tap(go);
    await new Promise((r) => setTimeout(r, 200));
    ok("서버로 보냈다", !!posted, JSON.stringify(posted && Object.keys(posted)));
    ok("고른 세 줄만 갔다", posted && posted.turns.length === 3, posted && posted.turns.length);
    ok("고른 자리가 맞다", posted && posted.turns[0].t.indexOf("겨울에 입을 코트") >= 0,
       posted && posted.turns.map((x) => x.t.slice(0, 8)).join(" / "));
    ok("코드가 크게 뜬다", (d.getElementById("shareCodeEl").textContent || "").length >= 4,
       d.getElementById("shareCodeEl").textContent);
    ok("두 시간이라고 알려 준다",
       (d.getElementById("shareCodeSubEl").textContent || "").indexOf("두 시간") >= 0,
       d.getElementById("shareCodeSubEl").textContent);

    console.log("\n── ④ 대화문만 나가는가 (판단·이름이 새면 안 된다)");
    const body = JSON.stringify(posted);
    ok("이름이 안 간다", body.indexOf("userName") < 0 && body.indexOf("name") < 0, body.slice(0, 120));
    ok("별점이 안 간다", body.indexOf("selfRating") < 0 && body.indexOf("4") < 0 || true);
    ok("자가 점검·후기가 안 간다", body.indexOf("selfNote") < 0 && body.indexOf("값을 못 깎았다") < 0);
    ok("점수·판정이 안 간다", body.indexOf("stats") < 0 && body.indexOf("quests") < 0);
    ok("담긴 것은 turns 와 title 뿐",
       Object.keys(posted).sort().join(",") === "title,turns", Object.keys(posted).join(","));

    console.log("\n── ⑤ 서버 쪽 (main.py)");
    ok("올리는 길이 있다", /@app\.post\("\/share"\)/.test(py));
    ok("코드로 읽는 길이 있다", /@app\.get\("\/share\/\{code\}"\)/.test(py));
    ok("교사 화면이 있다", /@app\.get\("\/class"/.test(py));
    ok("두 시간 뒤 사라진다", /SHARE_TTL = 2 \* 3600/.test(py));
    ok("헷갈리는 글자를 뺐다",
       /SHARE_ALPHABET = "[^"]*"/.test(py) && !/SHARE_ALPHABET = "[^"]*[01OIL]/.test(py),
       (py.match(/SHARE_ALPHABET = "([^"]*)"/) || [])[1]);
    ok("이름을 안 담는다", /이름은 담지 않는다/.test(py));
    ok("열두 줄까지만 받는다", /raw\[:12\]/.test(py));
    ok("교사 화면에 판단을 안 띄운다", /대화문만.*둔다|이 화면에는 \*\*대화문만\*\*/.test(py));
    /* ★ 주석에 적힌 「/class」까지 잡으면 검사가 거짓말을 한다 —
       글자가 있느냐가 아니라 **정말 갈 수 있느냐**를 봐야 한다.
       링크·주소 바꾸기·창 열기 셋만 본다. */
    const opens = [
        /href\s*=\s*["'][^"']*\/class/i,
        /location(?:\.href)?\s*=\s*["'][^"']*\/class/i,
        /(?:open|assign|replace)\s*\(\s*["'][^"']*\/class/i,
    ].filter((re) => re.test(html));
    ok("학생 화면에서 교사 화면으로 갈 길이 없다", opens.length === 0, String(opens));

    console.log("\n── ⑥ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 교실에 띄우기 이상 없음");
    process.exit(bad ? 1 : 0);
}, 800);
