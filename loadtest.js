// ─────────────────────────────────────────────────────────────
// 로드 검사 — templates/index.html을 브라우저 엔진(jsdom)에 실제로 올려
// '페이지를 여는 순간 나는 오류'를 배포 전에 잡는다.
//
// 왜 필요한가: v37~v41에서 선언 순서가 어긋난 상수 하나(vuBars) 때문에
// 스크립트가 중간에 죽었고, 그 뒤 코드가 통째로 실행되지 않아
// '서버에 연결 중'에서 멈추는 등 원인을 알 수 없는 증상이 이어졌다.
// `node --check`는 문법만 보므로 이런 실행 시점 오류를 못 잡는다.
//
// 쓰는 법:  npm i jsdom  후
//          node loadtest.js templates/index.html
// ─────────────────────────────────────────────────────────────
// 실제 index.html을 브라우저 엔진(jsdom)에 올려 '로드 시점 오류'를 잡는다.
// 이번 사고(vuBars TDZ)처럼 스크립트가 중간에 죽는 문제를 배포 전에 걸러 낸다.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");

const errors = [];
const vc = new (require("jsdom").VirtualConsole)();
vc.on("jsdomError", (e) => errors.push(e.message + (e.stack ? "\n    " + e.stack.split("\n")[1] : "")));
vc.on("error", (m) => errors.push("console.error: " + m));

// 브라우저에만 있는 것들 최소 스텁
const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "https://example.test/",
  virtualConsole: vc,
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

setTimeout(() => {
  const w = dom.window;
  // 스크립트가 끝까지 실행됐는지: 맨 마지막에 선언되는 것들이 살아 있는지로 확인
  let reached = "확인 불가";
  try { reached = typeof w.document.body.dataset.screen === "string" ? "OK" : "?"; } catch (e) {}
  if (errors.length) {
    console.log("❌ 로드 중 오류 " + errors.length + "건");
    errors.slice(0, 6).forEach((e) => console.log("   " + e.split("\n")[0]));
  } else {
    console.log("✅ 로드 오류 없음 — 스크립트가 끝까지 실행됨");
  }
  console.log("   body[data-screen] =", w.document.body.dataset.screen);
  process.exit(errors.length ? 1 : 0);
}, 2500);
