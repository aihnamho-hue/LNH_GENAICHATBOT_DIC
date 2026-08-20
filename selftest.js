// ─────────────────────────────────────────────────────────────
// 자가 점검 · 후기 (v141)
//   〈표 33〉의 요소를 학습자가 **스스로** 매기는 자리.
//   ★ 핵심은 순서다 — AI 판정보다 **앞**에 있어야 자기 평가가 안 오염된다.
//   화면을 실제로 돌려 넘겨 보고, 눌러 보고, 기록에 남는지까지 본다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let bad = 0; const errs = [], sent = [];
const ok = (m, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x))); if (!c) bad++; };

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errs.push(e.detail ? (e.detail.message || String(e.detail)) : e.message));
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/", virtualConsole: vc,
    beforeParse(w) {
        w.fetch = () => Promise.resolve({ ok: false, status: 0, json: () => Promise.resolve({}) });
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
    const tap = (el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
    try { w.eval('uiLang="ko"'); } catch (e) {}
    // 서버로 보내는 것을 가로챈다
    w.eval('ws = { readyState: 1, send: function(s){ (window.__sent = window.__sent || []).push(s); } };');

    console.log("── ① 장 차례가 맞는가 (자가 점검이 AI 판정보다 앞)");
    const pages = [...d.querySelectorAll("#rpResultOverlay .res-page")].map((p) => p.id);
    ok("주제 대화 여섯 장", pages.length === 6, pages.join(" "));
    const fpages = [...d.querySelectorAll("#freeFbOverlay .res-page")].map((p) => p.id);
    ok("자유 대화도 다섯 장", fpages.length === 5, fpages.join(" "));
    ok("자유 대화 마지막 장 번호", w.eval("FREE_LAST") === 4, w.eval("FREE_LAST"));
    ok("자유 대화 점도 다섯", d.querySelectorAll("#freeDots .res-dot").length === 5);
    const has = (i, sel) => !!d.querySelector("#resPage" + i + " " + sel);
    ok("0 별점", has(0, ".self-stars"));
    ok("1 요소 자가 점검", has(1, "#selfChkList"));
    ok("2 후기", has(2, "#selfNoteEl"));
    ok("3 점수·단계", has(3, ".result-cards"));
    ok("4 AI 판정", has(4, "#rpIdcList"));
    ok("5 총평", has(5, "#rpReviewEl"));
    ok("점이 여섯 개", d.querySelectorAll("#rpResultOverlay .res-dot").length === 6);
    ok("마지막 장 번호가 맞다", w.eval("RES_LAST") === 5, w.eval("RES_LAST"));

    console.log("\n── ② 호아랑이 권한 요소를 묻는가");
    // 이 대화에서 「말 주고받기」와 「모르는 말 넘어가기」를 권했다고 친다
    w.eval('questReset(); idcTouched = ["move", "strategy"];');
    w.eval("selfReset();");
    await new Promise((r) => setTimeout(r, 120));
    const els = w.eval("JSON.stringify(selfChkEls)");
    const list = JSON.parse(els);
    ok("셋에서 넷을 묻는다", list.length >= 3 && list.length <= 4, els);
    ok("권한 것이 맨 앞에 온다", list[0] === "move" && list[1] === "strategy", els);
    ok("교실 몫(비언어)은 안 묻는다", list.indexOf("nonverbal") < 0, els);
    ok("겹치지 않는다", new Set(list).size === list.length, els);
    const rows = [...d.querySelectorAll("#selfChkList .self-chk-row")];
    ok("줄이 그만큼 그려졌다", rows.length === list.length, rows.length + "/" + list.length);
    ok("이름이 학습자 말이다", rows[0].querySelector(".sc-nm").textContent.indexOf("말 주고받기") === 0,
       rows[0].querySelector(".sc-nm").textContent.slice(0, 24));

    console.log("\n── ③ 눌러 보면 기록에 남는가");
    const [yes] = rows[0].querySelectorAll(".sc-yn button");
    const no2 = rows[1].querySelectorAll(".sc-yn button")[1];
    tap(yes); tap(no2);
    await new Promise((r) => setTimeout(r, 60));
    ok("「했어요」에 불이 들어온다", yes.classList.contains("on"), yes.className);
    ok("「안 했어요」에도 들어온다", no2.classList.contains("on"), no2.className);
    const chk = JSON.parse(w.eval("JSON.stringify(selfCheck)"));
    ok("고른 것이 담긴다", chk[list[0]] === true && chk[list[1]] === false, JSON.stringify(chk));

    console.log("\n── ④ 후기가 담기는가");
    const ta = d.getElementById("selfNoteEl");
    ok("안내가 뜬다", (d.getElementById("selfNoteAskEl").textContent || "").length > 3);
    ok("건너뛰어도 된다고 말한다", (d.getElementById("selfNoteSubEl").textContent || "").indexOf("안 써도") >= 0,
       d.getElementById("selfNoteSubEl").textContent);
    ok("보기글이 있다", (ta.placeholder || "").length > 3, ta.placeholder);
    ta.value = "값을 깎는 말이 잘 안 나왔다";
    ta.dispatchEvent(new w.Event("input", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 600));
    ok("후기가 담긴다", w.eval("selfNote").indexOf("값을 깎는") >= 0, w.eval("selfNote"));

    console.log("\n── ⑤ 서버로 가는가");
    const msgs = (w.__sent || []).map((x) => { try { return JSON.parse(x); } catch (e) { return {}; } });
    const sc = msgs.filter((m) => m.type === "self_check").pop();
    ok("self_check 를 보냈다", !!sc, JSON.stringify(msgs.map((m) => m.type)));
    ok("요소 체크가 실렸다", !!sc && typeof sc.check === "object" && Object.keys(sc.check).length >= 2);
    ok("후기가 실렸다", !!sc && (sc.note || "").indexOf("값을 깎는") >= 0);
    ok("무엇을 물었는지도 실렸다", !!sc && Array.isArray(sc.els) && sc.els.length === list.length);

    console.log("\n── ⑥ 전사 파일에 남는가 (연구 자료)");
    // 대화가 하나도 없으면 전사 자체가 빈손이다 — 한 줄 심고 본다
    w.eval('transcriptLog.push({ who:"나", text:"안녕하세요", at:new Date() });'
         + ' sessionStartedAt = sessionStartedAt || new Date();');
    const txt = w.eval("buildTranscriptText()") || "";
    ok("스스로 점검 줄이 있다", txt.indexOf("스스로 점검") >= 0, txt.slice(-200).replace(/\n/g, " | "));
    ok("후기 줄이 있다", txt.indexOf("학습자 후기") >= 0);
    ok("논문 용어로 적힌다", txt.indexOf("대화이동 관리") >= 0 || txt.indexOf("의사소통 전략") >= 0);

    console.log("\n── ⑦ 새 대화를 열면 비워지는가");
    w.eval("questReset(); selfReset();");
    await new Promise((r) => setTimeout(r, 80));
    ok("체크가 비워진다", Object.keys(JSON.parse(w.eval("JSON.stringify(selfCheck)"))).length === 0);
    ok("후기가 비워진다", w.eval("selfNote") === "");
    ok("권한 요소도 비워진다", w.eval("idcTouched.length") === 0);

    console.log("\n── ⑧ 그리다 터진 곳");
    ok("오류 없음", errs.length === 0, errs.slice(0, 2).join(" / "));

    console.log(bad ? `\n💥 ${bad}건` : "\n🎉 자가 점검 이상 없음");
    process.exit(bad ? 1 : 0);
}, 800);
