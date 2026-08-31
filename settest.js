// settest.js — 설정 · 동의 · 소속 · 배경음 페이더 · 자유 대화 기억 (v152)
//
// ★ 왜 이 검사가 있나
//   ① 동의 여부가 **그냥 변수**였다. 새로 고칠 때마다 다시 뜨고
//     「언제 동의했다」가 아무 데도 안 남았다 — 연구 자료로 쓸 수가 없다.
//   ② 홈 위에 단추가 다섯이나 늘어서 있었다. 설정으로 모으되
//     **원래 단추를 지우지 않고 숨겨 두고 대신 누른다** — 지우면 조용히 터진다.
//   ③ 자유 대화 기억은 드라이브를 뒤지지 않는다. 기기에 두고 함께 보낸다.
//   ④ v153 — 소속·동의는 **닫힌 문**이다. 안 갖추면 대화로 못 들어간다.
//     v152 에서는 고르기를 닫으면 그냥 시작됐다 — 그 문은 문이 아니었다.

const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};
const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map(m => m[1]))];
const tbl = (name) => {
  const m = html.match(new RegExp("const " + name + "\\s*=\\s*\\{"));
  if (!m) return null;
  const seg = html.slice(m.index, html.indexOf("\n    };", m.index));
  return new Set([...seg.matchAll(/[\{\s,]([a-z]{2}):\s*[\"\{]/g)].map(x => x[1]));
};

console.log("── ① 문구가 지원 언어 전부에 ────────────────────");
["SET_MSG", "CN_MSG", "ORG_TXT"].forEach(n => {
  const g = tbl(n);
  ok(`${n} (${g ? g.size : 0}/${codes.length})`,
     !!g && codes.every(c => g.has(c)),
     g ? "빠진 언어: " + JSON.stringify(codes.filter(c => !g.has(c))) : "표가 없다");
});

// b2 는 「이름이 바뀌었어요」 — 다시 묻는 자리의 안내. 빠지면 영어로 뜬다
{
  const m = html.match(/const ORG_TXT\s*=\s*\{/);
  const seg = m ? html.slice(m.index, html.indexOf("\n    };", m.index)) : "";
  const has = new Set([...seg.matchAll(/[\{\s,]([a-z]{2}):\s*\{[^\n]*b2:/g)].map(x => x[1]));
  ok(`ORG_TXT.b2 (${has.size}/${codes.length})`, codes.every(c => has.has(c)),
     "빠진 언어: " + JSON.stringify(codes.filter(c => !has.has(c))));
}

console.log("\n── ② 동의를 기기에 남기는가 ─────────────────────");
ok("옛 변수(consentGiven)를 안 쓴다",
   !/^\s*let consentGiven/m.test(html), "새로 고치면 사라지는 값이었다");
ok("버전·시각·켜짐을 남긴다",
   /consent\.ver/.test(html) && /consent\.at/.test(html) && /consent\.on/.test(html));
ok("버전이 다르면 다시 받는다",
   /this\.ver === CONSENT_VER/.test(html), "문안을 고쳐도 안 물어보면 뜻이 없다");
ok("화면과 서버의 버전 이름이 둘 다 있다",
   /const CONSENT_VER = "([\d.]+)"/.test(html) && /CONSENT_DOC_VER = "([\d.]+)"/.test(py));
const v1 = (html.match(/const CONSENT_VER = "([\d.]+)"/) || [])[1];
const v2 = (py.match(/CONSENT_DOC_VER = "([\d.]+)"/) || [])[1];
ok(`두 버전이 같다 (${v1} / ${v2})`, v1 === v2,
   "어긋나면 동의서에 찍히는 버전과 실제가 다르다");
ok("자료마다 동의 기록이 함께 간다", /consent: CONSENT\.pack\(\)/.test(html));
ok("녹음을 끄면 소리를 안 올린다",
   /const hasAudio = CONSENT\.on && blob/.test(html),
   "껐는데도 올라가면 동의문이 거짓말이 된다");

console.log("\n── ③ 설정이 원래 단추를 대신 누르는가 ───────────");
/* ★ v155 — 여기가 이 판의 핵심이다.
   v152 는 `hidden` 속성이 붙어 있는지만 보고 통과했다. 그런데 화면에는
   **그대로 보이고 있었다** — `.home-top .home-ico { display: inline-flex }` 가
   브라우저 기본 규칙을 이겼기 때문이다. jsdom 은 이 어긋남을 못 잡는다
   (기본 규칙을 더 세게 친다). 그래서 **마크업을 직접 센다.** */
{
  const m = html.match(/<div class="home-top">[\s\S]*?<\/div>/);
  const bar = m ? m[0] : "";
  const ids = [...bar.matchAll(/id="([^"]+)"/g)].map((x) => x[1]);
  ok(`홈 위 줄에 단추가 둘뿐 (${ids.join(", ")})`,
     (bar.match(/<button/g) || []).length === 2
     && ids.includes("homeHistoryBtn") && ids.includes("homeSetBtn"),
     "안 보이게 하는 것으로는 모자랐다 — 아예 이 줄 밖으로 내보낸다");
  ["voiceBtn", "bgmBtn", "homeNameBtn", "homeLangBtn"].forEach((id) => {
    ok(`${id} 는 홈 줄 밖에 있다`, bar.indexOf('id="' + id + '"') < 0);
  });
  ok("대신 눌러 줄 자리는 남아 있다",
     /<div class="set-proxy"[\s\S]*?id="voiceBtn"[\s\S]*?id="homeLangBtn"[\s\S]*?<\/div>/.test(html),
     "지우면 이 아이디를 부르던 여러 자리가 조용히 터진다");
  ok("그 자리는 !important 로 잠갔다",
     /\.set-proxy \{ display: none !important; \}/.test(html));
  ok("숨김이 무엇보다 세다",
     /\[hidden\] \{ display: none !important; \}/.test(html),
     "`hidden` 은 기본 규칙이라 우리가 쓴 display 한 줄에 진다");
}
["homeNameBtn", "homeLangBtn", "voiceBtn", "bgmBtn"].forEach(id => {
  ok(`설정이 ${id} 를 대신 누른다`, new RegExp('clickHidden\\("' + id + '"\\)').test(html));
});

console.log("\n── ④ 소속·기억이 서버까지 닿는가 ───────────────");
ok("업로드에 소속을 싣는다", /fd\.append\("org", ORG\.id/.test(html));
ok("서버가 소속을 받는다", /org:\s*str = Form/.test(py));
// 파일 이름을 실제로 만들어 보는 대신, 소속 조각이 이름에 끼어드는지를 본다
ok("파일 이름에 소속이 들어간다",
   /f"_\{_tag\}" if _tag/.test(py) && /호아랑대화_\{kind\}/.test(py),
   "이름으로 정렬해야 기관별로 모인다");
ok("기억은 자유 대화만", /mode === "rp" \? "" : "&mem="/.test(html));
ok("서버가 mem 을 받는다", /past_mem = websocket\.query_params\.get\("mem"/.test(py));
ok("프롬프트에 얹는다", /name_hint \+ mem_hint/.test(py));
ok("첫 인사에서 한 번만 꺼낸다",
   /첫 인사에서[\s\S]{0,12}한 번만/.test(py) && /다시 꺼내지 마라/.test(py),
   "자꾸 꺼내면 감시받는다고 느낀다");
ok("추가 호출 없이 요약을 받는다",
   /"memory":\{\{"topics":\[\],"note":""\}\}/.test(py),
   "따로 부르면 판마다 돈이 더 든다");
ok("5분 넘은 판만 남긴다", /const MEM_MIN_SEC = 300/.test(html));
ok("동의서 쪽이 있다", /@app\.get\("\/consent"/.test(py));
ok("동의서는 인쇄로 PDF (서버에서 안 굽는다)",
   /window\.print\(\)/.test(py) && !/reportlab/.test(py));
ok("대화록 안쪽에도 소속을 적는다", /lines\.push\(" 소속: "/.test(html),
   "파일 이름은 옮기다 바뀐다. 안에 적힌 것은 남는다");
ok("모든 올리기가 소속을 함께 싣는다",
   /function appendCommonFields\(fd\)[\s\S]{0,600}fd\.append\("orgClass"/.test(html),
   "한 자리에서 붙여야 세 갈래(중간저장·끝·되돌리기)가 다 같다");

ok("소속 판번호를 서버로 보낸다", /fd\.append\("orgVer", ORG\.ver/.test(html));
ok("서버가 판번호를 받는다", /orgVer:\s*str = Form/.test(py));
ok("안 오면 v1 로 적는다", /_clean_str\(orgVer, 4\) or "1"/.test(py),
   "옛 화면에서 온 자료도 어느 이름표였는지 알 수 있어야 한다");
ok("대화록에도 판번호", /이름표 v/.test(html));
{
  // ★ 학습자가 보는 것은 ORG_LIST 뿐이다. 주석에 적힌 사연은 안 본다.
  const m = html.match(/const ORG_LIST = \[[\s\S]*?\];/);
  const seg = m ? m[0] : "";
  ok("학교 이름이 앞에 안 온다", !!seg && !/ko: "[^"]*대학교/.test(seg) && !/ko: "중앙대/.test(seg),
     "고를 것은 과정이지 학교가 아니다. 학교 이름이 앞에 오면 제 학교를 찾는다");
  ok("급수를 안 붙인다", !!seg && !/3단계|3급/.test(seg),
     "둘 다 3이라 가르는 데 아무 도움이 안 됐다");
}

console.log("\n── ④-2 목소리 ───────────────────────────────────");
ok("기본이 여자아이 (화면)", /localStorage\.getItem\("voicePref"\) \|\| "girl"/.test(html));
ok("기본이 여자아이 (서버)", /HOARANG_VOICE_KEY = "girl"/.test(py));
ok("여자아이는 Leda", /"girl":\s*"Leda"/.test(py));
ok("나이 번호를 || 로 안 받는다", !/AG\[voiceAgeOf\(voicePref\)\] \|\|/.test(html),
   "AG.young 은 0 이라 || 를 만나면 성인으로 미끄러진다");

console.log("\n── ⑤ 실제로 돌려 본다 ──────────────────────────");
const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/",
  beforeParse(w) {
    w.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve("") });
    w.matchMedia = w.matchMedia || (() => ({ matches: false, addEventListener() {}, addListener() {} }));
    w.scrollTo = () => {};
    w.HTMLElement.prototype.scrollIntoView = () => {};
    w.HTMLMediaElement.prototype.play = () => Promise.resolve();
    w.HTMLMediaElement.prototype.pause = () => {};
    w.HTMLMediaElement.prototype.load = () => {};
    w.open = () => null;
    try { w.localStorage.setItem("uiLang", "ko"); w.localStorage.setItem("userName", "바트"); } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const d = w.document;
  const P = (s) => { try { return w.eval(s); } catch (e) { return "ERR " + e.message; } };

  // 설정이 열리고 지금 값이 보이는가
  P('document.getElementById("homeSetBtn").click()');
  const ov = d.getElementById("setOverlay");
  ok("설정이 열린다", !!ov && !ov.classList.contains("hidden"));
  ok("이름이 보인다", (d.getElementById("setNameV").textContent || "") === "바트");
  ok("언어가 보인다", /한국어/.test(d.getElementById("setLangV").textContent || ""),
     d.getElementById("setLangV").textContent);
  ok("목소리가 보인다", (d.getElementById("setVoiceV").textContent || "").length > 1,
     d.getElementById("setVoiceV").textContent);
  ok("소속이 아직 없다고 알린다",
     (d.getElementById("setOrgV").textContent || "").length > 1);

  // 배경음 페이더
  ok("페이더가 있다", !!d.getElementById("setBgmVol"));
  const before = P("bgmTarget('chatBgm')");
  P('bgmVolSet(50)');
  const after = P("bgmTarget('chatBgm')");
  ok(`페이더가 실제 음량을 바꾼다 (${before} → ${after})`,
     typeof before === "number" && typeof after === "number" && after < before);
  ok("기기에 남는다", P('localStorage.getItem("bgmVol")') === "50");
  P('bgmVolSet(100)');

  // 동의
  ok("아직 동의 안 함", P("CONSENT.ok") === false);
  P("CONSENT.agree()");
  ok("동의하면 ok", P("CONSENT.ok") === true);
  ok("시각이 남는다", typeof P("CONSENT.at") === "string" && P("CONSENT.at").length > 10);
  ok("끄면 꺼진다", P("CONSENT.setOn(false); CONSENT.on") === false);
  ok("끈 때가 남는다", (P("CONSENT.offAt") || "").length > 10);
  P("CONSENT.setOn(true)");

  // 소속
  P('ORG.put("kiip","KIIP 사회통합프로그램","")');
  ok("소속이 남는다", /KIIP/.test(P("ORG.label()")), P("ORG.label()"));

  // 기억
  ok("짧은 판은 안 남긴다",
     P('memPut(120,{topics:["짧은판"],note:"x"}); memAll().length') === 0);
  ok("5분 넘으면 남긴다",
     P('memPut(600,{topics:["카페 아르바이트","고향 네팔"],note:"아르바이트 어떻게 됐는지"}); memAll().length') === 1);
  const brief = P("memBrief()");
  ok("보낼 한 줄이 만들어진다", /카페 아르바이트/.test(brief), brief);
  ok("적을 것이 없으면 안 남긴다",
     P('memPut(600,{topics:[],note:""}); memAll().length') === 1);

  // ★ v152 — 이미 동의한 학습자에게도 소속을 묻는가
  //   처음에는 동의 단추 뒤에만 묻는 자리를 두었더니, 어제까지 쓰던 학습자는
  //   그 길을 지나지 않아 **영영 안 물었다**. 동의와 별개의 관문이어야 한다.
  P('ORG.put("","","")');            // 소속을 지운다 (id/name/cls 는 읽기 전용)
  ok("지우면 안 고른 상태가 된다", P("ORG.ok") === false);
  P('window.__started = 0; window.startSession = function(){ window.__started++; };');
  P('requestStartWithConsent(null)');
  ok("이미 동의했어도 소속을 묻는다",
     !d.getElementById("orgOverlay").classList.contains("hidden"),
     "어제까지 쓰던 학습자의 자료가 소속 없이 쌓인다");
  ok("묻는 동안엔 대화가 아직 안 시작된다", P("window.__started") === 0);
  P('document.getElementById("orgX").click()');
  // ★ v153 — v152 는 여기서 대화가 시작됐다. 이제는 시작되지 않는다.
  ok("고르기를 닫으면 대화가 시작되지 않는다", P("window.__started") === 0,
     "소속 없는 자료가 섞이면 뒷날 갈라낼 축이 없다");
  P('ORG.put("kiip","KIIP 사회통합프로그램","")');
  P('requestStartWithConsent(null)');
  ok("한 번 고른 뒤엔 안 묻고 곧바로 시작한다", P("window.__started") === 1
     && d.getElementById("orgOverlay").classList.contains("hidden"));

  console.log("\n── ⑥ v153 관문 ─────────────────────────────────");
  // 홈 위에 남은 단추 — 지난 대화와 설정 둘뿐이어야 한다
  const top = [...d.querySelectorAll(".home-top button")].map((b) => b.id);
  ok("홈 위에는 지난 대화와 설정 둘뿐 (" + top.join(", ") + ")",
     top.length === 2 && top[0] === "homeHistoryBtn" && top[1] === "homeSetBtn");
  ok("설정이 여전히 넷을 대신 누른다",
     ["voiceBtn", "bgmBtn", "homeNameBtn", "homeLangBtn"]
       .every((id) => !!d.getElementById(id)),
     "화면에서만 뺀 것이지 지운 것이 아니다");

  // 목소리 이름표 — 「아이」가 「성인」으로 뜨던 자리
  P('voicePref = "boy"'); const vb = P("voiceLabelNow()");
  P('voicePref = "girl"'); const vg = P("voiceLabelNow()");
  P('voicePref = "woman"'); const vw = P("voiceLabelNow()");
  ok("남자아이가 아이로 뜬다 (" + vb + ")", /아이/.test(vb) && !/성인/.test(vb));
  ok("여자아이가 아이로 뜬다 (" + vg + ")", /아이/.test(vg) && !/성인/.test(vg));
  ok("성인은 그대로 성인 (" + vw + ")", /성인/.test(vw));

  // 관문 — 동의도 소속도 없는 상태에서 카드를 누른다
  P('CONSENT.ver=""; localStorage.removeItem("consent"); CONSENT.clear && CONSENT.clear();');
  P('lsPut("consent.ver",""); lsPut("consent.at",""); ORG.put("","","")');
  P('window.__rp = 0; window.__free = 0;');
  P('window.enterTopicSetup = function(){ window.__rp++; };');
  P('window.enterFreeChat  = function(){ window.__free++; };');
  ok("치우면 동의도 소속도 없다", P("CONSENT.ok") === false && P("ORG.ok") === false);

  P('document.getElementById("homeRpCard").click()');
  ok("주제 대화를 누르면 동의부터 묻는다",
     !d.getElementById("consentOverlay").classList.contains("hidden"));
  ok("아직 못 들어간다", P("window.__rp") === 0);

  P('document.getElementById("consentCancelBtn").click()');
  ok("취소하면 그대로 홈이다", P("window.__rp") === 0
     && d.getElementById("consentOverlay").classList.contains("hidden"));

  P('document.getElementById("homeFreeCard").click()');
  ok("자유 대화를 눌러도 다시 묻는다",
     !d.getElementById("consentOverlay").classList.contains("hidden") && P("window.__free") === 0,
     "한 번 취소했다고 다음부터 그냥 통과하면 문이 아니다");

  P('document.getElementById("consentAgreeBtn").click()');
  ok("동의하면 이어서 소속을 묻는다",
     !d.getElementById("orgOverlay").classList.contains("hidden") && P("window.__free") === 0);

  P('document.getElementById("orgX").click()');
  ok("소속을 닫으면 못 들어간다", P("window.__free") === 0,
     "★ v152 는 여기서 그냥 시작됐다 — 소속 없는 자료가 섞였다");

  P('document.getElementById("homeFreeCard").click()');
  ok("다시 누르면 소속만 다시 묻는다",
     !d.getElementById("orgOverlay").classList.contains("hidden")
     && d.getElementById("consentOverlay").classList.contains("hidden"),
     "동의는 이미 했으니 두 번 묻지 않는다");

  P('[...document.querySelectorAll("#orgList .org-opt")][0].click()');
  P('document.getElementById("orgOkBtn").click()');
  ok("고르고 나서야 들어간다", P("window.__free") === 1);
  ok("고른 것이 남는다", /KIIP/.test(P("ORG.label()")), P("ORG.label()"));

  P('document.getElementById("homeRpCard").click()');
  ok("다 갖춘 뒤엔 안 묻는다", P("window.__rp") === 1
     && d.getElementById("consentOverlay").classList.contains("hidden")
     && d.getElementById("orgOverlay").classList.contains("hidden"));

  ok("반 번호를 안 묻는다", d.getElementById("orgClassInput").hidden === true,
     "물음이 둘이면 아래 칸을 비워 두고 확인을 눌러, 반 있는 자료와 없는 자료가 섞인다");

  console.log("\n── ⑦ v154 이름표를 고쳤으니 다시 묻는다 ────────");
  const NEW = P('ORG_LIST.map(o => o.ko).join(" | ")');
  ok("새 이름표 (" + NEW + ")",
     /KIIP 사회통합프로그램/.test(NEW) && /언어교육원 한국어교육과정/.test(NEW)
     && /글로벌엘리트학부\(연세\)/.test(NEW));

  // 옛 판(v1)으로 골라 둔 학습자 — 손으로 넣어 흉내 낸다
  P('lsPut("org.id","cau"); lsPut("org.name","중앙대학교 언어교육원 (3급)"); lsPut("org.ver","1")');
  ok("옛 판은 「덜 갖춘 것」으로 본다", P("ORG.ok") === false && P("ORG.stale") === true,
     "이름표가 바뀌었으면 예전에 고른 것은 그 뜻이 아니다");
  P('window.__free = 0');
  P('document.getElementById("homeFreeCard").click()');
  ok("옛 판이면 다시 묻는다",
     !d.getElementById("orgOverlay").classList.contains("hidden") && P("window.__free") === 0);
  const body = d.getElementById("orgBodyEl").textContent || "";
  ok("바뀌었다고 알린다 (" + (P("uiLang") || "?") + ")",
     body === P("orgT('b2')") && body !== P("orgT('b')"),
     "「한 번만 고르면 됩니다」라 해 놓고 또 물으면 그 말이 거짓이 된다");
  ok("옛 선택을 미리 켜 두지 않는다",
     [...d.querySelectorAll("#orgList .org-opt")].every((b) => !b.classList.contains("on")),
     "헷갈려 고른 그 자리가 켜져 있으면 그대로 확인을 누른다");
  P("paintSettings()");
  ok("설정에도 「안 고름」으로 보인다",
     (d.getElementById("setOrgV").textContent || "") === P("setT('orgNone')"),
     d.getElementById("setOrgV").textContent);

  // 새로 고른다
  P('[...document.querySelectorAll("#orgList .org-opt")][0].click()');
  P('document.getElementById("orgOkBtn").click()');
  ok("새로 고르면 통과한다", P("ORG.ok") === true && P("window.__free") === 1);
  ok("판번호가 새로 남는다", P("ORG.ver") === P("ORG_VER"), P("ORG.ver"));
  ok("자료에 판번호가 실린다", P("JSON.stringify(ORG.pack())").indexOf('"ver"') > 0,
     P("JSON.stringify(ORG.pack())"));
  ok("고른 것은 KIIP", /KIIP/.test(P("ORG.label()")), P("ORG.label()"));

  P('document.getElementById("homeFreeCard").click()');
  ok("그 뒤로는 안 묻는다", P("window.__free") === 2);

  console.log();
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 설정 · 동의 · 소속 · 기억이 제자리에 있습니다");
  process.exit(0);
}, 900);
