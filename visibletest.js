// ─────────────────────────────────────────────────────────────
// 「안 보이는 단추」 잡기 (v143)
//
// ★ 왜 이 검사가 생겼나
//   v142 에서 「🏫 교실에 띄우기」 단추를 만들었는데 **화면에 안 떴다.**
//   코드는 멀쩡했고, jsdom 검사도 초록불이었다.
//   까닭은 CSS 한 줄이었다 —
//       .export-btn { display: none !important; }                            ← 전역
//       #histExportBtn:not(.hidden) { display: inline-block !important; }     ← 이것만 예외
//   새 단추도 .export-btn 을 달았으니 **처음부터 안 보이는 물건**이었다.
//
//   검사가 초록불이었던 까닭은 `classList.contains("hidden")` 만 봤기 때문이다.
//   「숨김 클래스가 없다」와 「눈에 보인다」는 다른 말이다.
//   jsdom 은 CSS 를 계산하지 않으므로 그 차이를 영영 못 본다.
//
// ★ 그래서 CSS 를 읽어 **통째로 죽은 클래스**를 찾고,
//   그 클래스를 단 요소 가운데 예외가 안 뚫린 것을 알린다.
// ─────────────────────────────────────────────────────────────
const fs = require("fs");
const csstree = require("css-tree");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let bad = 0;
const ok = (m, c, x) => {
    console.log((c ? "  ✅ " : "  ❌ ") + m + (c ? "" : "   " + (x === undefined ? "" : x)));
    if (!c) bad++;
};

const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
const ast = csstree.parse(css, { positions: true });

// ① display:none !important 를 거는 **홑 클래스 선택자**를 모은다 (.foo 하나짜리만)
const killed = new Map();       // 클래스 이름 -> 줄 번호
// ② 그것을 되살리는 선택자에 든 아이디를 모은다 (#bar…{display:…})
const revivedIds = new Set();

csstree.walk(ast, {
    visit: "Rule",
    enter(rule) {
        const decls = [];
        csstree.walk(rule.block, { visit: "Declaration", enter(d) { decls.push(d); } });
        const dis = decls.filter((d) => d.property === "display");
        if (!dis.length) return;
        const sel = csstree.generate(rule.prelude);
        const none = dis.some((d) => csstree.generate(d.value).trim() === "none" && d.important);
        if (none) {
            sel.split(",").forEach((one) => {
                const t = one.trim();
                if (/^\.[A-Za-z0-9_-]+$/.test(t)) killed.set(t.slice(1), rule.loc ? rule.loc.start.line : 0);
            });
            return;
        }
        // 되살리는 쪽 — 아이디가 들어 있으면 그 아이디는 예외가 뚫린 것
        const alive = dis.some((d) => csstree.generate(d.value).trim() !== "none");
        if (alive) (sel.match(/#([A-Za-z0-9_-]+)/g) || []).forEach((x) => revivedIds.add(x.slice(1)));
    },
});

console.log("── ① 통째로 죽은 클래스");
ok("찾았다", killed.size > 0, [...killed.keys()].join(", "));
[...killed.entries()].forEach(([c, ln]) => console.log(`     .${c}  (줄 ${ln})`));

console.log("\n── ② 「보이려고 하는데 안 보이는 것」이 있는가");
/* ★ 죽은 클래스를 단 것을 다 잡으면 검사가 뭉툭해진다 —
     .hidden 은 **숨기라고 만든 것**이고, .float-ham 처럼 일부러 감춘 것도 있다.
   진짜 위험한 자리는 딱 하나다 —
     ㄱ) 전역으로 죽은 클래스를 달았는데
     ㄴ) JS 가 그것을 **보이려고** .hidden 을 떼는데
     ㄷ) display 를 되살려 주는 규칙이 없다
   v142 의 「교실에 띄우기」가 정확히 이 꼴이었다. */
const bodyHtml = html.replace(/<style>[\s\S]*?<\/style>/g, "");
const script = (html.match(/<script>([\s\S]*)<\/script>/) || ["", ""])[1];
const found = [];
[...killed.keys()].forEach((cls) => {
    if (cls === "hidden") return;              // 숨기라고 만든 것은 건너뛴다
    const re = new RegExp(`<[^>]*class="[^"]*\\b${cls}\\b[^"]*"[^>]*>`, "g");
    let m;
    while ((m = re.exec(bodyHtml))) {
        const tag = m[0];
        const id = (tag.match(/\sid="([^"]+)"/) || [])[1] || "";
        if (!id) continue;
        // JS 가 이것을 보이려고 하는가 (.hidden 을 떼거나 갈아 끼우는가)
        const wants = new RegExp(
            `["']${id}["'][\\s\\S]{0,200}?classList\\.(remove|toggle)\\(\\s*["']hidden["']`
        ).test(script) || new RegExp(
            `${id}\\.classList\\.(remove|toggle)\\(\\s*["']hidden["']`
        ).test(script);
        if (wants) found.push({ cls, id, revived: revivedIds.has(id), tag: tag.slice(0, 78) });
    }
});
console.log(`     보이려고 하는 것 ${found.length}개`);
found.forEach((x) => console.log(
    `     ${x.revived ? "보임  " : "✗안 보임"}  .${x.cls}  #${x.id}`));
const dead = found.filter((x) => !x.revived);
ok("보이려고 하는데 CSS 가 막는 것이 없다", dead.length === 0,
   dead.map((x) => `#${x.id} (.${x.cls} 에 막힘 — 되살리는 규칙이 없다)`).join(" | "));

console.log("\n── ③ 일부러 숨긴 단추 목록이 그대로인가");
/* ★ 클래스가 아니라 **아이디로** 죽이면 사고가 안 난다 — 이름을 적어야 죽으니까.
   그래도 목록이 슬그머니 늘어나면 곤란하다. 여기에 못 박아 둔다.
   늘리거나 줄일 때는 이 줄도 같이 고치게 된다 = **알고 하게 된다.** */
const WANT_HIDDEN = ["exportBtn", "inappCopyBtn", "consentCancelBtn", "rpCancelBtn",
                     "rpEditBtn", "prSkipBtn", "prCloseBtn", "notifNoBtn",
                     "voiceCloseBtn", "appDlCloseBtn"];
const killedIds = new Set();
csstree.walk(ast, {
    visit: "Rule",
    enter(rule) {
        let none = false;
        csstree.walk(rule.block, { visit: "Declaration", enter(d) {
            if (d.property === "display" && d.important
                && csstree.generate(d.value).trim() === "none") none = true;
        } });
        if (!none) return;
        const sel = csstree.generate(rule.prelude);
        sel.split(",").forEach((one) => {
            const t = one.trim();
            if (/^#[A-Za-z0-9_-]+$/.test(t)) killedIds.add(t.slice(1));
        });
    },
});
const got = [...killedIds].sort().join(",");
ok(`일부러 숨긴 것이 열 개 그대로다 (${killedIds.size}개)`,
   got === WANT_HIDDEN.slice().sort().join(","), got);
ok("지난 기록 내보내기는 살아 있다", !killedIds.has("histExportBtn"));

console.log("\n── ④ 되살린 규칙이 .hidden 을 안 짓밟는가");
/* v84 에서 !important 로 되살렸다가 .hidden 이 영영 안 먹은 적이 있다.
   되살리는 규칙이 있다면 :not(.hidden) 이 붙어 있어야 한다. */
const revives = [];
csstree.walk(ast, {
    visit: "Rule",
    enter(rule) {
        const sel = csstree.generate(rule.prelude);
        if (!/#/.test(sel)) return;
        let hit = false;
        csstree.walk(rule.block, { visit: "Declaration", enter(d) {
            if (d.property === "display" && d.important
                && csstree.generate(d.value).trim() !== "none") hit = true;
        } });
        if (hit) revives.push(sel);
    },
});
revives.forEach((sel) => {
    ok(`${sel} 이 .hidden 을 비켜 준다`, /:not\(\.hidden\)/.test(sel), sel);
});
if (!revives.length) console.log("     (되살리는 규칙 없음 — 클래스로 안 죽이니 되살릴 것도 없다)");

console.log(bad ? `\n💥 ${bad}건` : "\n🎉 안 보이는 단추 없음");
process.exit(bad ? 1 : 0);
