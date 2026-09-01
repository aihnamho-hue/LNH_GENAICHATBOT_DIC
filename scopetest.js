// scopetest.js — 연구 범위를 IDC 아홉 요소로 한정했는가 (v158)
//
// ★ 왜 이 검사가 있나
//   이 챗봇이 기르려는 것은 **상호작용 대화 능력**이지 발화의 정확성이 아니다.
//   그런데 v157까지 지시문은 조사·시제·높임·어휘를 **대화 중에 고치라**고 시켰다.
//
//   그것이 왜 문제인가 —
//   ① IDC 아홉 요소 어디에도 들어가지 않는다.
//   ② 4.1.2에서 기존 앱 넷이 「대화 중에 오류를 지적하지 않는 것」을
//     몰입을 위한 교육적 처리로 평가해 두었는데 이 챗봇만 반대로 간다.
//   ③ 제5장에서 「교정이 있었으니 나아진 것 아니냐」를 막을 수 없게 된다.
//
//   그리고 다른 하나 — 목표 없는 자유 대화는 범용 생성형 AI와 다르지 않다.
//   목표를 **학습자가** 고르게 하고, 서버는 그 자리를 만들 뿐이다.

const fs = require("fs");
const { JSDOM } = require("jsdom");
const html = fs.readFileSync("app.html", "utf8");
const py = fs.readFileSync("main.py", "utf8");
let fail = 0;
const ok = (n, c, why) => {
  console.log((c ? "  ✅ " : "  ❌ ") + n + (c ? "" : "   " + (why || "")));
  if (!c) fail++;
};

console.log("── ① 정확성을 고치지 않는가 ────────────────────");
ok("정확성 비교정을 못 박았다", /정확성은 고치지 않는다/.test(py));
ok("무엇을 안 고치는지 적었다",
   /조사\(에\/에서, 을\/를\)·시제·높임·어미·어순·어휘 선택이 틀려도/.test(py));
ok("「더 자연스러운 표현」도 금지", /「더 자연스러운 표현」을 알려 주지도 마라/.test(py));
ok("옛 지시가 남아 있지 않다",
   !/\[즉시 교정\]/.test(py) && !/그 자리에서 바로 교정해줘/.test(py),
   "한 곳만 고치고 상황극 쪽을 두면 주제 대화에서만 첨삭이 돈다");
ok("상황극 쪽도 같다", /\[정확성 비교정\] 규칙은 상황극 중에도 그대로다/.test(py));
ok("왜 안 고치는지 적어 두었다", /말이 막히는 자리/.test(py),
   "까닭이 없으면 다음 판에서 도로 들어간다");

console.log("\n── ①-2 되말하기 (v159) ─────────────────────────");
ok("되말하기를 시킨다", /되말하기 — 고쳐 주는 것이 아니라/.test(py));
ok("이해 확인 표시로 규정했다", /교정이 아니라 「이해 확인 표시」다/.test(py));
ok("「더 좋아요」를 막았다",
   /"이렇게 말하면 더 좋아요" \/ "다시 말해볼래요\?" 는 \*\*하지 마라\.\*\*/.test(py),
   "되말하기와 명시적 교정은 다르다 — 둘을 섞으면 다시 첨삭이 된다");
ok("알아차리는 것은 학습자의 몫", /알아차리는 것은 학습자의 몫이다/.test(py));
ok("한 차례에 하나만", /한 차례에 하나만/.test(py));
ok("취향 차이는 되말하지도 않는다", /뜻이 통하는데 취향만 다르면 \*\*되말하지도 마라/.test(py));
ok("상황극에서는 배역 안에서", /배역 안에서 바른 꼴로 되말해라/.test(py));

console.log("\n──   되말한 자리를 뒤에 보여 준다 ──────────────");
ok("recasts 칸이 프롬프트에 있다",
   /"recasts":\[\{\{"me":"","fix":"","part":""\}\}\]/.test(py));
ok("실제로 되말한 것만", /호아랑이 실제로 되말한 자리만 적어라/.test(py));
ok("바르게 말한 것은 안 적는다", /처음부터 바르게 말한 것은 적지 마라/.test(py));
ok("발음은 안 다룬다", /발음·억양은 다루지 않는다/.test(py));
ok("셋까지", /\(data or \{\}\)\.get\("recasts"\) or \[\]\)\[:3\]/.test(py));
ok("같은 것이면 버린다", /if not me or not fix or me == fix:/.test(py));
ok("조각이 바른 꼴 안에 있어야 색을 칠한다",
   /part if part and part in fix else ""/.test(py),
   "없는 조각에 불을 켜려 하면 엉뚱한 데가 빨개진다");
ok("★ 점수에는 안 들어간다", /점수에는 들어가지 않는다/.test(py),
   "정확성을 재기 시작하면 연구 범위를 다시 넘는다");
ok("추가 호출이 없다", /같은 호출\*\*에서 함께 받았다[\s\S]{0,200}recasts/.test(py)
   || /recasts = \[\][\s\S]{0,60}for rc in \(\(data or \{\}\)/.test(py));
ok("final_score 로 함께 내려간다", /"recasts": idc\.get\("recasts"\) or \[\]/.test(py));
ok("화면이 받는다", /recasts: msg\.recasts \|\| \[\]/.test(html));
ok("지난 대화에 남는다", /recasts: \(rpFinal && rpFinal\.recasts\) \|\| \[\]/.test(html));
ok("대화록에도 남는다", /되말해 준 것:/.test(html));
ok("달라진 조각에만 불", /em\.className = "rc-hit"/.test(html));
ok("빨간색은 그 조각만", /\.hlrn-rc \.rc-hit \{ color: #C0392B/.test(html));
ok("대화 중에는 표시하지 않는다",
   !/rc-hit/.test(html.split("function flushBubble")[1] || ""),
   "말풍선에 색을 칠하면 그것은 첨삭이 되고 말하기가 멈춘다");

console.log("\n── ② 그래도 단절은 다룬다 (repair) ─────────────");
ok("뜻이 안 통할 때만 나선다", /말이 통하지 않을 때만 나선다/.test(py));
ok("고쳐 주지 않고 되묻는다", /되물어서 학습자가 스스로 다시 말하게/.test(py));
ok("두 번 막히면 한 번만 일러 준다", /두 번 넘게 막히면 그때 한 번만/.test(py));
ok("모국어 전환은 전략으로 다룬다",
   /의사소통 전략\(모국어 전환\)/.test(py),
   "모국어 대응을 지우면 안 된다 — 그것은 IDC 요소다");
ok("천천히·다시·쉽게·빨리는 그대로", /\[천천히\]/.test(py) && /\[쉽게\]/.test(py)
   && /\[빨리\/빨리빨리\]/.test(py),
   "이것은 정확성 교정이 아니라 의사소통 단절 수정이다");
ok("사후 판정은 여덟 요소 그대로",
   /IDC_SCORED_KEYS = \[e\["key"\] for e in IDC_TRAINABLE\]/.test(py));
ok("판정 원칙이 기능 중심", /상호작용 기능의 수행 여부.*문법이 틀려도 기능을 해냈으면 인정/s.test(py));

console.log("\n── ③ 자유 대화의 목표 ──────────────────────────");
ok("서버가 focus 를 받는다", /focus_els = \{k for k in/.test(py));
ok("아는 요소만 받는다", /if k in IDC_SCORED_KEYS\}/.test(py));
ok("프롬프트에 얹는다", /\+ build_focus_block\(focus_els\)/.test(py));
ok("고른 것이 없으면 아무것도 안 붙는다",
   /def build_focus_block[\s\S]{0,900}if not focus:\s*\n\s*return ""/.test(py));
ok("이름을 입에 올리지 못하게 막았다",
   /이름을 입에 올리지 마라[\s\S]{0,80}연습해요/.test(py),
   "「오늘은 화제 관리를 연습해요」라고 하면 그것은 과제이지 대화가 아니다");
ok("자리를 대신 채우지 못하게 막았다", /그 자리를 네가 대신 채우지 마라/.test(py));
ok("울타리가 아니라 우선순위", /우선순위이지 울타리가 아니다/.test(py));
ok("넛지를 고를 때 앞세운다",
   /return \(0 if el in focus_els else 1,/.test(py));
ok("후보를 좁히지는 않는다", /후보를 좁히지는 않는다/.test(py),
   "억지로 끼워 넣으면 맥락 없이 따라 읽히는 자리로 돌아간다");
ok("자유 대화에만 보낸다", /mode === "rp" \|\| !freeFocus\.length \? ""/.test(html));
ok("대화록에 남는다", /이번에 해 볼 것: /.test(html));
ok("기록에도 남는다", /focus: \(mode === "rp" \? \[\] : freeFocus\.slice\(\)\)/.test(html));
{
  const m = html.match(/const FG_TXT = \{[\s\S]*?\n    \};/);
  const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map((x) => x[1]))];
  const has = new Set([...(m ? m[0] : "").matchAll(/[\{\s,]([a-z]{2}):\s*\{/g)].map((x) => x[1]));
  ok(`목표 고르기 문구가 지원 언어 전부에 (${has.size}/${codes.length})`,
     codes.every((c) => has.has(c)), "빠진 언어: " + JSON.stringify(codes.filter((c) => !has.has(c))));
}

console.log("\n── ⑤ v160 — 갈래 · 화계 · 동의 승계 · 화면 ─────");
ok("잡담에는 용건·협상을 안 낸다",
   /TASK_ONLY = \{"qInitiate", "qCounter", "qRefuse", "qAlt", "qCond", "qHold"\}/.test(py));
ok("서버가 갈래를 본다", /is_task = bool\(rp_plan\)/.test(py)
   && /if not is_task and qid in TASK_ONLY:/.test(py));
ok("목적 대화에는 잡담용을 안 낸다", /if is_task and qid in CHAT_MOVE:/.test(py));
ok("잡담용 대화이동 둘을 만들었다",
   /"id": "qOpinion"/.test(py) && /"id": "qDiffer"/.test(py),
   "move 여섯이 다 용건·협상이면 잡담에서 이 요소를 못 기른다");
ok("의견 자리 표지를 만들었다", /buckets\.append\(\["qOpinion", "qDiffer", "qExpand"\]\)/.test(py));
ok("물어봤을 때 갈래로 갈린다",
   /"qCounter" if is_task else "qOpinion"/.test(py),
   "「무슨 과목이 어려워?」에 「용건을 말해 보세요!」가 뜨던 자리");
ok("화면 목록도 갈래를 안다",
   /id:"qOpinion",[\s\S]{0,90}mode:"free"/.test(html)
   && /id:"qDiffer",[\s\S]{0,90}mode:"free"/.test(html));
{
  const codes = [...new Set([...html.matchAll(/data-lang="([a-z]{2})"/g)].map((x) => x[1]))];
  const n = (html.match(/qOpinion:"/g) || []).length;
  ok(`잡담 넛지 문구가 지원 언어 전부에 (${n}/${codes.length})`, n === codes.length);
}
ok("문형도 있다", /qOpinion:\s*\["저는 이렇게 생각합니다/.test(html));

ok("화계는 명시적으로 고쳐 준다",
   /화계만은 명시적으로 고쳐 준다/.test(py) && /다시 말할 기회를 준다/.test(py),
   "화계는 학습자가 스스로 정한 조건이고 「맥락·정체성 인식」 그 자체다");
ok("화계 교정도 두세 번까지만", /한 대화에서 \*\*두세 번까지만\.\*\*/.test(py));
ok("감탄사는 안 잡는다", /감탄사·혼잣말[\s\S]{0,40}잡지 마라/.test(py));
ok("배역을 깨지 않는다", /배역을 깨지 말고/.test(py));

ok("동의를 매 판마다 다시 안 받는다", /const CONSENT_CARRY = \["1\.0"\]/.test(html));
ok("승계는 손으로 적은 것만", /CONSENT_CARRY\.indexOf\(this\.ver\) >= 0/.test(html),
   "적지 않으면 저절로 다시 받는다 — 뜻이 넓어지는 변경은 다시 받아야 한다");
ok("기록에는 실제 동의한 버전이 남는다", /ver: this\.ver/.test(html),
   "1.0 에 동의한 사람은 1.0 으로 남아야 정직하다");

ok("폰에서 대화 화면이 한 화면에 든다",
   /body\[data-screen="chat"\] \{ height: 100vh; height: 100dvh/.test(html));
ok("채팅 안쪽 스크롤은 그대로", /body\[data-screen="chat"\] \.chat-panel \{ min-height: 0/.test(html));
ok("시작·종료 단추는 붙박이", /\.character-panel \.main-controls \{ flex: 0 0 auto; margin-top: auto/.test(html),
   "그것까지 스크롤해서 찾아야 하면 대화를 못 끝낸다");

console.log("\n── ④ 실제로 눌러 본다 ──────────────────────────");
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
    try {
      w.localStorage.setItem("uiLang", "ko");
      w.localStorage.setItem("userName", "바트");
      w.localStorage.setItem("consent.ver", "1.1");
      w.localStorage.setItem("consent.at", "2026-08-30T10:00:00+09:00");
      w.localStorage.setItem("consent.on", "1");
      w.localStorage.setItem("org.id", "kiip");
      w.localStorage.setItem("org.name", "KIIP 사회통합프로그램");
      w.localStorage.setItem("org.ver", "2");
    } catch (e) {}
  },
});
const w = dom.window;

setTimeout(() => {
  const d = w.document;
  const P = (s) => { try { return w.eval(s); } catch (e) { return "ERR " + e.message; } };

  ok("관문은 이미 지났다", P("CONSENT.ok") === true && P("ORG.ok") === true);
  P("window.__free = 0; window.enterFreeChat_real = enterFreeChat;");
  P('document.getElementById("homeFreeCard").click()');
  ok("자유 대화를 누르면 목표부터 묻는다",
     !d.getElementById("fgOverlay").classList.contains("hidden"));

  const opts = [...d.querySelectorAll("#fgList .fg-opt")];
  ok(`고를 것이 여섯 (${opts.length})`, opts.length === 6);
  ok("쉬운 이름과 학술 이름이 함께",
     /막혔을 때|되살리기/.test(opts.map((o) => o.textContent).join(" "))
     && /의사소통 단절 수정/.test(opts.map((o) => o.textContent).join(" ")),
     opts.map((o) => o.textContent.replace(/\s+/g, " ")).join(" | ").slice(0, 90));

  opts[0].click();
  ok("하나 고르면 켜진다", opts[0].classList.contains("on") && P("freeFocus.length") === 1);
  opts[1].click();
  ok("둘까지 된다", P("freeFocus.length") === 2);
  opts[2].click();
  ok("셋은 안 된다", P("freeFocus.length") === 2 && !opts[2].classList.contains("on"),
     "셋을 고르면 아무것도 안 고른 것과 같다");
  opts[0].click();
  ok("다시 누르면 꺼진다", P("freeFocus.length") === 1 && !opts[0].classList.contains("on"));

  const line = P("fgGoalLine()");
  ok("한 줄로 만들어진다 (" + line + ")", typeof line === "string" && line.length > 1);

  P('document.getElementById("fgOkBtn").click()');
  ok("확인하면 목표가 남는다", P("freeFocus.length") === 1);
  ok("창이 닫힌다", d.getElementById("fgOverlay").classList.contains("hidden"));

  // 건너뛰기
  P("openFreeGoal(null)");
  P('[...document.querySelectorAll("#fgList .fg-opt")][0].click()');
  ok("다시 열면 지난 선택이 안 남는다", P("freeFocus.length") === 1);
  P('document.getElementById("fgSkipBtn").click()');
  ok("건너뛰면 목표가 비워진다", P("freeFocus.length") === 0,
     "목표를 강제하면 그것은 과제이지 자유 대화가 아니다");

  // 대화록에 남는가
  P('mode = "free"; freeFocus = ["repair", "topic"];');
  P('sessionStartedAt = new Date(); transcriptLog = [{role:"user", text:"안녕하세요", time:"00:01"}];');
  const txt = String(P("buildTranscriptText()"));
  const gl = txt.split("\r\n").find((l) => l.indexOf("이번에 해 볼 것") >= 0) || "";
  console.log("     " + gl.trim());
  ok("대화록에 한국어로 남는다", /막혔을 때 되살리기/.test(gl) && /이야깃거리 이끌기/.test(gl));
  P('freeFocus = [];');
  ok("안 골랐으면 그렇게 적힌다",
     /\(안 고름\)/.test(String(P("buildTranscriptText()"))));

  // 되말한 자리가 복습 카드에 그려지는가
  P(`window.__hist = [{ ts:"2026-09-01T08:00:00.000Z", mode:"free", title:"자유 대화",
        preview:"…", text:"[00:01] 나:\\n  네\\n", turns:[],
        learn:{ review:"", idc:[], idcTotal:0, phrases:[],
                recasts:[{me:"학교에 공부해요", fix:"학교에서 공부해요", part:"에서"},
                          {me:"어제 밥 먹어요", fix:"어제 밥 먹었어요", part:""}] } }];
     localStorage.setItem("masamasaHistory", JSON.stringify(window.__hist));`);
  P("openHistory()");
  const hit = d.querySelector("#histList .hist-item");
  if (hit) hit.click();
  const rc = [...d.querySelectorAll("#histList .hlrn-rc")];
  ok(`되말한 자리가 둘 그려진다 (${rc.length})`, rc.length === 2);
  if (rc.length) {
    const hitEm = rc[0].querySelector(".rc-hit");
    ok("달라진 조각에만 불이 켜진다 (" + (hitEm ? hitEm.textContent : "") + ")",
       !!hitEm && hitEm.textContent === "에서");
    ok("원래 말도 함께 보인다",
       /학교에 공부해요/.test(rc[0].querySelector(".rc-me").textContent));
    ok("조각을 못 받으면 통째로 보인다",
       !rc[1].querySelector(".rc-hit")
       && /어제 밥 먹었어요/.test(rc[1].querySelector(".rc-fix").textContent),
       "없는 조각에 불을 켜려 하면 엉뚱한 데가 빨개진다");
  }

  console.log();
  try { w.close(); } catch (e) {}
  if (fail) { console.log(`💥 실패 ${fail}건`); process.exit(1); }
  console.log("🎉 범위가 IDC 아홉 요소로 한정되었고, 자유 대화에 목표가 생겼습니다");
  process.exit(0);
}, 900);
