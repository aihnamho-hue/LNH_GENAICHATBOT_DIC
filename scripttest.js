// 대화문 듣기 화면 검사 — 연습 전에 모델 대화를 듣는 자리(v60)
// ① 대화문이 있으면 줄·기능단계 구분선·역할 이름이 그려지는가
// ② 줄을 누르면 그 줄만 재생되고 모국어가 펼쳐지는가
// ③ 학습자 역과 상대 역을 다른 목소리로 읽는가
// ④ 대화문 생성이 실패했을 때(빈 목록) 듣기를 건너뛰고 대화 단계로 가는가
// ⑤ 전체 재생 중에는 ▶가 ⏸로 바뀌고 흔들림이 멈추는가
// ⑥ 🪜 비계 버튼과 영상통화 기능단계가 주제 대화에서만 보이는가
const fs = require("fs"), path = require("path");
const { JSDOM } = require("jsdom");
const SRC = process.argv[2] || path.join(__dirname, "templates", "index.html");
const html = fs.readFileSync(SRC, "utf8");
let fail = 0;
const ok = (c, m) => { console.log((c ? "  ✅ " : "  ❌ ") + m); if (!c) fail++; };

const ttsCalls = [];
const dom = new JSDOM(html, {
    runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
    beforeParse(w) {
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
        w.HTMLMediaElement.prototype.load = () => {};
        w.AudioContext = w.webkitAudioContext = function () {
            return { state: "running", sampleRate: 24000, currentTime: 0, resume: () => Promise.resolve(),
                close: () => Promise.resolve(), createBuffer: () => ({ getChannelData: () => new Float32Array(1) }),
                createBufferSource: () => ({ connect(){}, start(){}, stop(){}, buffer: null }),
                createGain: () => ({ connect(){}, gain: { value: 1, setValueAtTime(){}, linearRampToValueAtTime(){} } }),
                createOscillator: () => ({ connect(){}, start(){}, stop(){}, frequency: { setValueAtTime(){}, exponentialRampToValueAtTime(){} }, type: "" }),
                destination: {}, audioWorklet: { addModule: () => Promise.resolve() } };
        };
        w.navigator.mediaDevices = { getUserMedia: () => Promise.resolve({ getTracks: () => [] }) };
        w.MediaRecorder = function () {}; w.MediaRecorder.isTypeSupported = () => false;
        w.WebSocket = function () { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
        w.WebSocket.CONNECTING = 0; w.WebSocket.OPEN = 1; w.WebSocket.CLOSING = 2; w.WebSocket.CLOSED = 3;
        // /tts 호출을 가로채 어떤 목소리로 무엇을 읽었는지 기록한다
        w.fetch = (url, opt) => {
            if (String(url).includes("/tts")) {
                try { ttsCalls.push(JSON.parse(opt.body)); } catch (e) {}
                return Promise.resolve({ ok: true, arrayBuffer: () => Promise.resolve(new ArrayBuffer(64)) });
            }
            return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
        };
        w.speechSynthesis = { cancel(){}, speak(){}, getVoices: () => [] };
        w.matchMedia = w.matchMedia || (() => ({ matches: false, addListener(){}, removeListener(){} }));
        w.scrollTo = () => {};
    },
});

const PLAN = {
    topic_ko: "물건 사기", goal_ko: "옷 사기", place_ko: "옷 가게",
    user_role: "손님", ai_role: "점원",
    stages: [{ name: "인사", native: "Greeting", desc: "", expressions: [] },
             { name: "물건 고르기", native: "Choosing", desc: "", expressions: [] },
             { name: "계산", native: "Paying", desc: "", expressions: [] }],
    script: [
        { speaker: "ai", text: "어서 오세요!", native: "Welcome!", stage: 0 },
        { speaker: "user", text: "안녕하세요, 옷 좀 보려고요.", native: "Hi, I'd like to look at clothes.", stage: 0 },
        { speaker: "ai", text: "네, 뭐 찾으세요?", native: "Sure, what are you looking for?", stage: 1 },
        { speaker: "user", text: "이거 다른 색도 있어요?", native: "Does this come in other colors?", stage: 1 },
        { speaker: "ai", text: "네, 파란색도 있어요.", native: "Yes, we have blue too.", stage: 1 },
        { speaker: "user", text: "이거 주세요. 얼마예요?", native: "I'll take this. How much?", stage: 2 },
    ],
};

setTimeout(async () => {
    const w = dom.window, d = w.document;

    console.log("── ① 대화문 렌더 ──");
    w.eval(`rpPlan = ${JSON.stringify(PLAN)}; showScript();`);
    const overlay = d.getElementById("rpScriptOverlay");
    ok(!overlay.classList.contains("hidden"), "듣기 화면이 열린다");
    const lines = [...d.querySelectorAll("#rpScriptList .sc-line")];
    ok(lines.length === 6, `줄 ${lines.length}개 (6개여야)`);
    const heads = [...d.querySelectorAll("#rpScriptList .sc-stage")];
    ok(heads.length === 3, `기능 단계 구분선 ${heads.length}개 (단계 3개여야)`);
    ok(/1\. 인사/.test(heads[0].textContent), "구분선에 단계 이름이 붙는다: " + heads[0].textContent.trim());
    const mine = lines.filter(el => el.classList.contains("mine"));
    ok(mine.length === 3, `내가 할 줄 ${mine.length}개가 구분된다 (3개여야)`);
    ok(/손님/.test(lines[1].querySelector(".sc-who").textContent), "역할 이름이 보인다");
    ok(lines[0].querySelector(".sc-native").textContent === "Welcome!", "모국어가 담겨 있다");
    ok(!lines[0].classList.contains("open"), "모국어는 처음엔 접혀 있다");

    console.log("\n── ② 줄 탭 = 그 줄만 다시 듣기 + 모국어 펼침 ──");
    ttsCalls.length = 0;
    lines[3].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    await new Promise(r => setTimeout(r, 250));
    ok(lines[3].classList.contains("open"), "누른 줄의 모국어가 펼쳐진다");
    ok(lines[3].classList.contains("on"), "누른 줄이 강조된다");
    ok(ttsCalls.length === 1, `TTS 호출 ${ttsCalls.length}회 (1회여야 — 그 줄만)`);
    ok(ttsCalls[0] && ttsCalls[0].text === "이거 다른 색도 있어요?", "누른 줄의 문장을 읽는다");
    lines[3].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    await new Promise(r => setTimeout(r, 150));
    ok(!lines[3].classList.contains("open"), "다시 누르면 모국어가 접힌다");

    console.log("\n── ③ 역할별 목소리 구분 ──");
    // 캐시 때문에 호출 순서가 어긋날 수 있으니 문장으로 찾는다
    const find = (txt) => ttsCalls.find(c => c.text === txt) || {};
    for (const key of ["auto", "girl"]) {   // 학습자가 고른 목소리를 바꿔 가며
        ttsCalls.length = 0;
        w.eval(`voicePref = "${key}"; ttsMem.clear();`);
        lines[2].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));   // 점원(ai)
        await new Promise(r => setTimeout(r, 200));
        lines[3].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));   // 손님(user)
        await new Promise(r => setTimeout(r, 200));
        const vAi = find("네, 뭐 찾으세요?").voice, vMe = find("이거 다른 색도 있어요?").voice;
        ok(vAi !== vMe, `홈 선택="${key}" → 상대="${vAi}" ↔ 나="${vMe}" 목소리가 다르다`);
    }
    ok(find("네, 뭐 찾으세요?").role === "점원", "상대 역은 배역 이름을 넘겨 목소리를 고른다");
    w.eval(`voicePref = "auto";`);

    console.log("\n── ④ 전체 재생 상태 ──");
    const playBtn = d.getElementById("rpScPlayBtn");
    ok(d.getElementById("rpScPlayIco").textContent === "▶", "처음엔 ▶");
    playBtn.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    await new Promise(r => setTimeout(r, 200));
    ok(playBtn.classList.contains("playing"), "재생 중에는 흔들림이 멈춘다(.playing)");
    ok(d.getElementById("rpScPlayIco").textContent === "⏸", "재생 중에는 ⏸");
    playBtn.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
    await new Promise(r => setTimeout(r, 200));
    ok(!playBtn.classList.contains("playing"), "다시 누르면 멈춘다");
    ok(![...d.querySelectorAll("#rpScriptList .sc-line")].some(el => el.classList.contains("on")),
       "멈추면 강조가 사라진다");

    console.log("\n── ⑤ 대화문이 없으면 건너뛴다 ──");
    d.getElementById("rpScriptOverlay").classList.add("hidden");
    d.getElementById("rpBriefOverlay").classList.add("hidden");
    w.eval(`rpPlan = ${JSON.stringify({ ...PLAN, script: [] })}; showScript();`);
    await new Promise(r => setTimeout(r, 150));
    ok(d.getElementById("rpScriptOverlay").classList.contains("hidden"), "듣기 화면이 안 뜬다");
    ok(!d.getElementById("rpBriefOverlay").classList.contains("hidden"), "곧바로 대화 단계로 간다");

    console.log("\n── ⑥ 🪜 비계 · 영상통화 기능단계 ──");
    const dock = d.getElementById("scfDock");
    ok(!!dock, "🪜 도크가 존재한다");
  // v93 — 넓은 화면에서는 왼쪽 기둥으로 옮겨 가므로 슬롯(#scfHomeSlot)으로 감쌌다.
  //        좁은 화면에서의 자리는 그대로다: 슬롯이 천천히·다시 버튼 바로 위에 있다.
  ok(dock.parentElement && dock.parentElement.id === "scfHomeSlot",
     "🪜가 자리 옮김 슬롯 안에 있다");
  ok(dock.parentElement.nextElementSibling &&
     dock.parentElement.nextElementSibling.classList.contains("quick-bar"),
     "그 슬롯이 천천히·다시 버튼 바로 위에 있다");
  ok(!!d.getElementById("scfSideSlot"), "넓은 화면용 자리(왼쪽 기둥)도 있다");
    ok(dock.classList.contains("hidden"), "주제 대화 전에는 숨어 있다");
    const hvSt = d.getElementById("hvStages");
    ok(!!hvSt && hvSt.hasAttribute("hidden"), "영상통화 기능단계도 처음엔 숨어 있다");
    w.eval(`rpSessionActive = true; rpPercent = 40;
            rpStagesState = ${JSON.stringify(PLAN.stages.map((s, i) => ({ name: s.name, native: s.native, done: i === 0 })))};
            renderProgress();`);
    ok(!d.getElementById("hvStages").hidden, "주제 대화가 시작되면 영상통화에도 단계가 뜬다");
    ok(d.querySelectorAll("#hvStChips .stage-chip").length === 3, "영상통화 단계 칩 3개");
    ok(d.getElementById("hvStPct").textContent === "40%", "영상통화에도 진행률이 같이 뜬다");
    ok(d.getElementById("hvStBar").style.width === "40%", "진행 막대도 따라간다");

    console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 대화문 듣기 이상 없음");
    process.exit(fail ? 1 : 0);
}, 1500);
