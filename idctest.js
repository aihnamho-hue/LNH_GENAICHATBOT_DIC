// 상호작용 대화 능력(IDC) 연결 검사 — 서버가 보내는 것과 화면이 그리는 것이 맞물리는가
// ① main.py의 IDC_ELEMENTS key ↔ index.html의 idc_<key> 사전이 12개 언어에서 일치하는가
// ② 서버가 총점에서 빼는 요소(media="class")를 화면도 등급 없이 그리는가
// ③ renderIdcProfile이 실제 페이로드로 행을 그려내는가 (jsdom)
// ④ 비계 페이딩 상수가 서버와 어긋나지 않는가
const fs = require("fs"), vm = require("vm"), path = require("path");
const ROOT = path.join(__dirname);
const SRC = process.argv[2] || path.join(ROOT, "templates", "index.html");
const PY = process.argv[3] || path.join(ROOT, "main.py");
const html = fs.readFileSync(SRC, "utf8");
const py = fs.readFileSync(PY, "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
const LANGS = ["ko", "en", "zh", "ja", "vi", "th", "id", "mn", "uz", "ru", "es", "fr"];
let fail = 0;

// ── 서버에서 요소 목록 뽑기 ──
const block = py.slice(py.indexOf("IDC_ELEMENTS = ["), py.indexOf("IDC_BY_KEY"));
const keys = [...block.matchAll(/"key":\s*"([a-z]+)"/g)].map(m => m[1]);
const classKeys = [...block.matchAll(/"key":\s*"([a-z]+)",[^}]*?"media":\s*"class"/gs)].map(m => m[1]);
console.log("── ① 서버 요소 ↔ 화면 사전 ──");
console.log(`  서버 IDC_ELEMENTS: ${keys.length}개 [${keys.join(", ")}]`);
if (keys.length !== 9) { fail++; console.log("  ❌ 논문 〈표 33〉은 9요소다"); }

// ── 화면 사전 실행 ──
const start = script.indexOf("const I18N = {");
let last = -1, re = /for \(const _l(?:ng)? in I18N_[A-Z0-9]+\) \{[^\n]*\n/g, m;
while ((m = re.exec(script))) last = m.index + m[0].length;
const ctx = { console }; vm.createContext(ctx);
vm.runInContext(script.slice(start, last) + "\n;globalThis.__I18N=I18N;", ctx);
const I18N = ctx.__I18N;
for (const l of LANGS) {
    const miss = keys.map(k => "idc_" + k).filter(k => !(k in (I18N[l] || {})));
    if (miss.length) { fail++; console.log(`  ❌ ${l} — ${miss.join(", ")} 없음`); }
}
if (!fail) console.log(`  ✅ 12개 언어 × ${keys.length}요소 이름 전부 존재`);

console.log("\n── ② 교실 전담 요소(총점 제외) ──");
console.log(`  서버가 빼는 요소: [${classKeys.join(", ") || "없음"}]`);
if (!classKeys.includes("nonverbal")) { fail++; console.log("  ❌ 비언어적 행위는 ✕(교실 전담)여야 한다"); }
else if (!/idcNote/.test(script)) { fail++; console.log("  ❌ 화면에 제외 안내(idcNote)가 없다"); }
else console.log("  ✅ 서버가 빼고, 화면이 그 이유를 알린다");

console.log("\n── ③ 결과 화면 렌더 ──");
(async () => {
    const { JSDOM } = require("jsdom");
    // 브라우저에만 있는 것들 최소 스텁 — 없으면 스크립트가 중간에 죽어 함수가 안 생긴다
    // (loadtest.js와 같은 스텁. 여기서는 렌더 함수까지 도달하는 것이 목적)
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
            w.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
            w.speechSynthesis = { cancel(){}, speak(){}, getVoices: () => [] };
            w.matchMedia = w.matchMedia || (() => ({ matches: false, addListener(){}, removeListener(){} }));
            w.scrollTo = () => {};
        },
    });
    await new Promise(r => setTimeout(r, 1200));
    const w = dom.window;
    const items = keys.map((k, i) => ({
        key: k, name: "서버이름" + i, layer: "macro",
        grade: k === "nonverbal" ? "na" : ["hi", "mid", "lo"][i % 3],
        why: k === "nonverbal" ? "" : "근거 발화 " + i,
        scored: k !== "nonverbal",
    }));
    try {
        w.eval(`renderIdcProfile(${JSON.stringify(items)}, 72);`);
    } catch (e) { fail++; console.log("  ❌ renderIdcProfile 호출 실패:", e.message); return done(); }
    const rows = w.document.querySelectorAll("#rpIdcList .idc-row");
    console.log(`  행 ${rows.length}개 (요소 ${keys.length}개여야)`);
    if (rows.length !== keys.length) fail++;
    const na = w.document.querySelectorAll("#rpIdcList .idc-row.na");
    console.log(`  등급 없는 행 ${na.length}개 (교실 전담 ${classKeys.length}개여야)`);
    if (na.length !== classKeys.length) fail++;
    const head = w.document.getElementById("idcHead");
    const note = w.document.getElementById("idcNoteEl");
    if (head.style.display === "none") { fail++; console.log("  ❌ 제목이 안 보인다"); }
    if (!note.textContent.trim()) { fail++; console.log("  ❌ 제외 안내가 비어 있다"); }
    const sub = w.document.getElementById("idcSubEl").textContent;
    if (!/72/.test(sub)) { fail++; console.log("  ❌ 총점이 안 보인다:", sub); }
    // 요소 이름이 서버 원문이 아니라 사전 번역으로 나오는가
    const first = rows[0].querySelector(".idc-name").textContent;
    if (/서버이름/.test(first)) { fail++; console.log("  ❌ 사전 번역 대신 서버 이름이 나온다:", first); }
    else console.log(`  ✅ 사전 번역으로 렌더 ("${first}")`);
    // 빈 배열이면 통째로 숨어야 한다 (자유 수다·분석 실패)
    w.eval("renderIdcProfile([], 0);");
    if (w.document.getElementById("idcHead").style.display !== "none") {
        fail++; console.log("  ❌ 항목이 없는데 제목이 남아 있다");
    } else console.log("  ✅ 항목이 없으면 통째로 숨는다");
    done();

    function done() {
        console.log("\n── ④ 비계 페이딩 상수 ──");
        const lv = (py.match(/IDC_LEVEL_MODEL = (\d)[\s\S]*?IDC_LEVEL_PROMPT = (\d)[\s\S]*?IDC_LEVEL_SOLO = (\d)/) || []);
        console.log(`  모델링 ${lv[1]} → 촉진 ${lv[2]} → 자율 ${lv[3]}`);
        if (!(Number(lv[1]) > Number(lv[2]) && Number(lv[2]) > Number(lv[3]))) {
            fail++; console.log("  ❌ 비계 수준이 내려가는 순서가 아니다");
        } else console.log("  ✅ 도움이 줄어드는 방향으로 정렬됨");
        console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 IDC 연결 이상 없음");
        process.exit(fail ? 1 : 0);
    }
})();
