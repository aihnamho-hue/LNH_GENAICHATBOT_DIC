// ─────────────────────────────────────────────────────────────
// 교실 화면 (v143)
//   대화가 끝나면 **저절로** 올라가고, 교사는 목록에서 골라 본다.
//   ★ 교사 화면을 main.py 에서 꺼내 **실제로 돌려** 눌러 본다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let bad = 0; const errs = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

// ── ① 대화가 끝나면 저절로 올라가는가 ──
console.log("── ① 대화가 끝나면 저절로 올라가는가");
let sent = null;
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = (u, o) => {
            if (String(u).indexOf("/class-log") >= 0) {
                try { sent = JSON.parse(o.body); } catch (e) { sent = {}; }
                return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true }) });
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
    },
});
const w = dom.window;

setTimeout(async () => {
    const d = w.document;
    try { w.eval('uiLang="ko"'); } catch (e) {}
    // 대화 한 판을 흉내 내고 저장한다
    w.eval(`
        userName = "바트";
        sessionStartedAt = new Date();
        transcriptLog.length = 0;
        transcriptLog.push({ role:"model", text:"어서 오세요.", time:"14:00" });
        transcriptLog.push({ role:"user",  text:"코트를 보려고요.", time:"14:01" });
        transcriptLog.push({ role:"model", text:"이 회색이 잘 나가요.", time:"14:01" });
        saveConversationToHistory();
    `);
    await new Promise((r) => setTimeout(r, 200));
    ok("학습자가 아무것도 안 눌러도 올라간다", !!sent, JSON.stringify(sent && Object.keys(sent)));
    ok("이름이 실린다", sent && sent.name === "바트", sent && sent.name);
    ok("대화문이 통째로 실린다", sent && sent.turns.length === 3, sent && sent.turns.length);
    ok("누가 말했는지 갈려 있다",
       sent && sent.turns[0].r === "ham" && sent.turns[1].r === "me",
       sent && sent.turns.map((x) => x.r).join(","));
    ok("판을 알아볼 열쇠가 있다", sent && "sid" in sent);
    ok("점수·자가 점검은 안 간다",
       JSON.stringify(sent).indexOf("selfCheck") < 0 && JSON.stringify(sent).indexOf("stats") < 0);
    ok("옛 코드 방식은 화면에서 걷혔다",
       html.indexOf("shareOverlay") < 0 && html.indexOf("histShareBtn") < 0);

    // ── ② 학술 용어가 화면에 안 뜨는가 ──
    console.log("\n── ② 학술 용어가 학습자 화면에 안 뜨는가");
    const HARD = ["상호작용", "대화이동 관리", "화제 관리", "차례 관리",
                  "의사소통 단절", "맥락·정체성", "기능 단계", "비언어적 행위"];
    /* ★ v144 — HOME_IDC 를 빠뜨려서 홈 카드에 「상호작용」이 그대로 남아 있었다.
       화면 말이 담긴 표는 세 개다. 셋을 다 훑는다. */
    const I = w.eval("I18N"), D = w.eval("IDC_TXT"), H = w.eval("HOME_IDC");
    const leak = [];
    Object.keys(H).forEach((lg) => (H[lg] || []).forEach((v, i) => {
        if (HARD.some((x) => String(v).indexOf(x) >= 0)) leak.push("HOME." + lg + "[" + i + "] = " + String(v).slice(0, 30));
    }));
    Object.keys(I).forEach((lg) => Object.keys(I[lg]).forEach((k) => {
        const v = String(I[lg][k] || "");
        if (HARD.some((x) => v.indexOf(x) >= 0)) leak.push(lg + "." + k + " = " + v.slice(0, 30));
    }));
    Object.keys(D).forEach((lg) => Object.keys(D[lg]).forEach((k) => {
        const v = String(D[lg][k] || "");
        if (HARD.some((x) => v.indexOf(x) >= 0)) leak.push("IDC." + lg + "." + k + " = " + v.slice(0, 30));
    }));
    ok("화면 말 사전에 논문 용어가 없다", leak.length === 0, leak.slice(0, 3).join(" | "));
    w.eval("openIdcList()");
    await new Promise((r) => setTimeout(r, 200));
    ok("요소 목록 제목이 채워진다",
       (d.getElementById("idcListTitleEl").textContent || "").length > 2,
       d.getElementById("idcListTitleEl").textContent);
    const cards = [...d.querySelectorAll("#idcCards .idc-card")];
    ok("카드에 논문 용어가 안 붙는다",
       cards.every((c) => !(c.querySelector(".idc-c2").textContent || "").trim()),
       cards.map((c) => c.querySelector(".idc-c2").textContent).join("|").slice(0, 40));
    ok("카드 이름은 학습자 말이다",
       cards[0].querySelector(".idc-c1").textContent === "말 주고받기",
       cards[0].querySelector(".idc-c1").textContent);
    ok("홈 카드도 학습자 말", (w.eval('idcT("home")') || "").indexOf("상호작용") < 0,
       w.eval('idcT("home")'));

    console.log("\n── ②-2 온보딩이 두 번까지만 뜨는가");
    /* 처음 쓸 때는 안내가 있어야 하지만, 세 번째부터는 길을 막는 벽이 된다.
       기기에 세어 두므로 새로 고쳐도 그대로다. */
    try { w.localStorage.removeItem("obSeen"); } catch (e) {}
    w.eval("introShown = false;");
    ok("아직 안 봤으면 뜬다", w.eval("obSeenCount()") === 0);
    w.eval("showIntroPopup();");
    await new Promise((r) => setTimeout(r, 60));
    ok("첫 번째 — 떴다", !d.getElementById("introOverlay").classList.contains("hidden"));
    ok("한 번 셌다", w.eval("obSeenCount()") === 1, w.eval("obSeenCount()"));
    w.eval("closeIntro(); introShown = false; showIntroPopup();");
    await new Promise((r) => setTimeout(r, 60));
    ok("두 번째 — 또 뜬다", !d.getElementById("introOverlay").classList.contains("hidden"));
    ok("두 번 셌다", w.eval("obSeenCount()") === 2, w.eval("obSeenCount()"));
    w.eval("closeIntro(); introShown = false; showIntroPopup();");
    await new Promise((r) => setTimeout(r, 60));
    ok("세 번째 — 안 뜬다", d.getElementById("introOverlay").classList.contains("hidden"));
    ok("더 안 센다", w.eval("obSeenCount()") === 2, w.eval("obSeenCount()"));
    ok("여섯 장짜리다", w.eval("OB_ART.length") === 6, w.eval("OB_ART.length"));

    // ── ③ 아이디가 겹치지 않는가 ──
    console.log("\n── ③ 아이디가 문서에 하나뿐인가");
    const seen = {}, dups = [];
    [...d.querySelectorAll("[id]")].forEach((el) => {
        if (seen[el.id]) { if (dups.indexOf(el.id) < 0) dups.push(el.id); }
        seen[el.id] = 1;
    });
    ok("겹치는 아이디가 없다", dups.length === 0, dups.join(", "));

    // ── ④ 교사 화면을 꺼내 돌려 본다 ──
    console.log("\n── ④ 교사 화면이 정말 도는가");
    const mm = py.match(/async def class_screen\(\)[\s\S]*?return HTMLResponse\(f"""([\s\S]*?)"""\)/);
    ok("교사 화면을 꺼낼 수 있다", !!mm);
    if (mm) {
        const chtml = mm[1].split("{{").join("{").split("}}").join("}").split("{APP_VERSION}").join("vTEST");
        const cerr = [];
        const cvc = new VirtualConsole();
        cvc.on("jsdomError", (e) => cerr.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
        const LIST = { ok: true, n: 2, items: [
            { id: "a1", name: "바트", title: "옷 가게", mode: "rp", turns: 6, at: "14:02" },
            { id: "b2", name: "린",   title: "",       mode: "free", turns: 4, at: "14:10" }] };
        const ONE = { ok: true, name: "바트", title: "옷 가게", turns: [
            { r: "ham", t: "어서 오세요." }, { r: "me", t: "코트를 보려고요." },
            { r: "ham", t: "이 회색이 잘 나가요." }] };
        const cdom = new JSDOM(chtml, {
            runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/class",
            virtualConsole: cvc,
            beforeParse(cw) {
                cw.fetch = (u) => String(u).indexOf("/class-one/") >= 0
                    ? Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(ONE) })
                    : Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LIST) });
            },
        });
        const cw = cdom.window, cd = cw.document;
        await new Promise((r) => setTimeout(r, 300));
        const btns = [...cd.querySelectorAll("#side .who-btn")];
        ok("그날 목록이 왼쪽에 뜬다", btns.length === 2, btns.length);
        ok("이름이 보인다", btns[0].textContent.indexOf("바트") >= 0, btns[0].textContent.slice(0, 24));
        ok("시각·줄수도 보인다", btns[0].textContent.indexOf("14:02") >= 0);
        ok("몇 명분인지 알려 준다", (cd.getElementById("cnt").textContent || "").indexOf("2") >= 0,
           cd.getElementById("cnt").textContent);
        btns[0].dispatchEvent(new cw.MouseEvent("click", { bubbles: true }));
        await new Promise((r) => setTimeout(r, 300));
        const msgs = [...cd.querySelectorAll("#m .msg")];
        ok("고르면 대화문이 크게 뜬다", msgs.length === 3, msgs.length);
        ok("학습자 줄이 오른쪽에 선다", msgs.length === 3 && msgs[1].className.indexOf("me") >= 0);
        ok("학습자 이름으로 부른다", cd.getElementById("m").textContent.indexOf("바트") >= 0);
        // v144 — 호아랑은 「호아랑」 석 자가 아니라 **얼굴**로 선다
        const faces = [...cd.querySelectorAll("#m .face")];
        ok("호아랑이 얼굴로 나온다", faces.length === 2, faces.length);
        ok("얼굴 그림이 있는 파일이다", faces.every((f) => /ham_idle\.png/.test(f.getAttribute("src"))),
           faces.map((f) => f.getAttribute("src")).join(" "));
        ok("호아랑 글자는 안 붙는다", cd.getElementById("m").textContent.indexOf("호아랑") < 0);
        ok("머리에 호아랑 아이콘", !!cd.querySelector("header .logo"));
        ok("점수·판정은 안 뜬다", cd.getElementById("m").textContent.indexOf("점") < 0);
        ok("교사 화면에서 터진 곳 없음", cerr.length === 0, cerr.slice(0, 2).join(" / "));
    }
    ok("학생 화면에서 교사 화면으로 갈 길이 없다",
       ![/href\s*=\s*["'][^"']*\/class/i,
         /location(?:\.href)?\s*=\s*["'][^"']*\/class(?!-)/i,
         /(?:open|assign|replace)\s*\(\s*["'][^"']*\/class(?!-)/i].some((re) => re.test(html)));

    console.log("\n── ⑤ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 교실 화면 이상 없음");
    process.exit(bad ? 1 : 0);
}, 800);
