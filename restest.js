/* v88 — 결과 네 장 · 자기 성찰 별점 · 말투 일관성 · 발화 연습 마이크 */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
const py = fs.readFileSync(process.argv[3] || "/sessions/gifted-youthful-edison/mnt/음성 대화형 챗봇/main.py", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

console.log("── ①⑥ 대화문이 페이더 말투를 따른다 ──");
ok("setup 이 페이더 좌표를 받는다", /d_val = _clamp_int\(body\.get\("d"\)/.test(py));
ok("클라이언트가 D·P 를 보낸다", /d: Number\(distSlider\.value\)/.test(html));
ok("말투 지시가 프롬프트에 실린다", /\[★ 말투 — 이것을 어기면/.test(py) && /\{style_line\}/.test(py));
ok("존댓말·반말·auto 세 갈래", /style == "polite"/.test(py) && /style == "banmal"/.test(py));
ok("화자별 말투를 코드가 정한다", /want_user = "banmal" if \(close and p_val >= 45\)/.test(py));
ok("정한 말투를 어긴 줄을 찾는다", /def _style_offenders/.test(py));
ok("어긴 줄만 골라 고쳐 쓴다", /async def _fix_style/.test(py)
   && /await _fix_style\(plan, want_user, want_ai\)/.test(py));
ok("고친 뒤 발화 연습도 다시 잇는다", /_fix_style[\s\S]{0,2200}?_link_expr_to_script/.test(py));
ok("발화 연습을 대화문에 잇는다", /def _link_expr_to_script/.test(py)
   && /_link_expr_to_script\(stages, script\)/.test(py));

console.log("── ③ 발화 연습은 대화이동 연습이다 ──");
ok("표현 태그에서 기능 단계 제외", /EXPR_IDC_KEYS = \[k for k in IDC_SCORED_KEYS if k != "stage"\]/.test(py));
ok("태그 기본값은 대화이동", /idc = "move"/.test(py));
ok("생성 지시에도 기능 단계 금지", /기능 단계'는 여기서 기를 수 없으니 쓰지 마라/.test(py));

console.log("── ② 발화 연습 마이크 ──");
ok("탭·꾹 누르기 둘 다", /PR_TAP_MS/.test(html) && /prTapMode = true/.test(html));
ok("너무 짧으면 다르게 안내", /t\("prTooShort"\)/.test(html));
ok("자동 종료 20초", /}, 20000\); \/\/ 안전 자동 종료/.test(html));

console.log("── ④⑤ 결과 네 장 ──");
ok("총평을 서버가 만든다", /async def run_review/.test(py) && /"review": review/.test(py));
ok("총평을 맨 먼저 시작해 흘려보낸다", /review_task = asyncio\.create_task\(_review_job\(\)\)/.test(py)
   && /generate_content_stream/.test(py) && /"type": "review_chunk"/.test(py));
ok("판정 실패해도 요소 칸을 비우지 않는다", /누적 횟수로 대체/.test(py));
ok("총평은 목록 아닌 줄글", /목록·번호·표를 쓰지 마라/.test(py));
// v101 — 문구를 박아 두지 않는다. 금지 목록이 실제로 있는지, 급수 제한이 있는지를 본다.
const _rv = (py.match(/async def run_review[\s\S]{0,4000}/)||[""])[0];
ok("총평도 어려운 말 금지", /연구 용어는 절대 금지/.test(_rv) && /레지스터/.test(_rv) && /대화이동/.test(_rv));
ok("총평 어휘를 급수로 묶는다", /1~4급 어휘·문법/.test(_rv));
ok("바꿔 쓰기 예시를 준다", /바꿔 써라/.test(_rv));

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "https://x.test/",
    beforeParse(w) {
        w.localStorage.setItem("skipEntryGuide", "1");
        w.HTMLMediaElement.prototype.play = () => Promise.resolve();
        w.HTMLMediaElement.prototype.pause = () => {};
        w.fetch = () => Promise.reject(new Error("no net"));
        w.Element.prototype.scrollIntoView = () => {};
    } });

setTimeout(() => {
    const d = dom.window.document;
    const pv = d.getElementById("resPrevBtn"), nx = d.getElementById("resNextBtn"),
          cl = d.getElementById("rpCloseBtn");
    const on = (i) => !d.getElementById("resPage" + i).classList.contains("hidden");

    console.log("── 쪽 넘기기 ──");
    d.getElementById("rpResultOverlay").classList.remove("hidden");
    dom.window.eval("resGo(0)");
    ok("첫 장은 자기 성찰", on(0) && !on(1) && !on(2) && !on(3));
    ok("첫 장엔 '이전'이 없다", pv.classList.contains("hidden"));
    ok("첫 장의 '다음'은 한 칸을 다 쓴다", nx.classList.contains("wide"));

    nx.click();
    ok("→ 대화 흐름", on(1) && !pv.classList.contains("hidden") && !nx.classList.contains("wide"));
    nx.click();
    ok("→ 상호작용 대화 능력", on(2));
    nx.click();
    ok("→ 총평", on(3) && nx.classList.contains("hidden") && !cl.classList.contains("hidden"));
    pv.click();
    ok("← 되돌아온다", on(2) && cl.classList.contains("hidden"));

    console.log("── 자기 성찰 별점 ──");
    dom.window.eval("resGo(0)");
    const stars = d.querySelectorAll("#resPage0 .self-star");
    ok("물어보는 말이 있다", (d.getElementById("selfAskEl").textContent || "").length > 3);
    stars[3].click();
    ok("네 개까지 칠해진다", d.querySelectorAll("#resPage0 .self-star.on").length === 4);
    ok("점수에 맞는 말이 뜬다", (d.getElementById("selfWordEl").textContent || "").length > 2);
    stars[1].click();
    ok("다시 누르면 줄어든다", d.querySelectorAll("#resPage0 .self-star.on").length === 2);
    ok("기록에 별점을 남긴다", /selfRating: selfRating \|\| 0/.test(html));

    console.log("── 자유 대화도 같은 것을 받는다 ──");
    ok("자유 대화에 별점", d.querySelectorAll("#freeFbOverlay .self-star").length === 5);
    ok("자유 대화에 총평", !!d.getElementById("freeReviewEl"));

    console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
    process.exit(fail ? 1 : 0);
}, 800);
