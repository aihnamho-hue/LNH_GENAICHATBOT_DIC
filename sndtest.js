/* sndtest.js — 소리와 '접힌 페이더 한 줄' (v113)
   ① 음량 15% · 나머지도 같은 비율
   ② 홈 배경음 무작위 — 파일이 다 있고 크기가 고르며 무겁지 않은가
   ③ 접힌 페이더 대신 남는 한 줄 */
const fs = require("fs"), path = require("path");
const html = fs.readFileSync("app.html", "utf8");
let bad = 0;
const ok = (t, c, x) => { console.log((c ? "  ✅ " : "  ❌ ") + t + (c || x === undefined ? "" : "   " + x)); if (!c) bad++; };

console.log("── ① 음량 ──");
const V = /const BGM_VOL = \{ bgm: ([\d.]+), prBgm: ([\d.]+), chatBgm: ([\d.]+) \}/.exec(html);
ok("배경음 셋 다 15%", !!V && V.slice(1).every(x => Number(x) === 0.15), V && V.slice(1).join("/"));
const G = /const GONG_VOL = ([\d.]+)/.exec(html);
ok("징도 같은 비율(0.5×0.75=0.375)", !!G && Number(G[1]) === 0.375, G && G[1]);
ok("징 음량이 한 곳에서만 정해진다", (html.match(/= 0\.5;/g) || []).length === 0
                                   && (html.match(/GONG_VOL/g) || []).length >= 3);
// const 는 끌어올려지지 않는다 — 쓰는 곳보다 위에 있어야 한다 (v110 에서 겪은 함정)
ok("GONG_VOL 선언이 쓰는 곳보다 위", html.indexOf("const GONG_VOL") < html.indexOf("gongSfx.volume = GONG_VOL"));
ok("더킹 비율은 그대로(0.15)", /const DUCK_RATIO = 0\.15;/.test(html));

console.log("── ② 홈 배경음 무작위 ──");
const L = /const HOME_BGM = \[([\s\S]*?)\];/.exec(html);
const files = L ? [...L[1].matchAll(/"\/static\/([^"?]+)/g)].map(m => m[1]) : [];
ok("여러 곡이 목록에 있다", files.length >= 3, files.join(" "));
ok("무작위로 고른다", /HOME_BGM\[Math\.floor\(Math\.random\(\) \* HOME_BGM\.length\)\]/.test(html));
/* ★ v114 — v113에서 preload="none" 으로 뒀다가 **배경음이 아예 안 났다.**
   아직 아무것도 안 받아 온 요소를 createMediaElementSource 로 물리면
   사파리가 소리를 안 내보낸다. 가벼움은 preload 가 아니라
   **src 를 하나만 꽂는 것**으로 이미 얻고 있었다. 되돌리지 않도록 못 박는다. */
ok("src 를 비워 두고 고른 하나만 꽂는다", /<audio id="bgm" loop preload="auto">/.test(html)
                                        && !/id="bgm"[^>]*src=/.test(html));
ok("꽂은 뒤 load() 로 밀어 준다", /bgm\.setAttribute\("src"[\s\S]{0,900}bgm\.load\(\)/.test(html));
ok("그래프에 물리기 전에도 밀어 준다", /el\.readyState === 0\) \{ try \{ el\.load\(\)/.test(html));
/* ★ v126 — static/ 이 통째로 없는 자리(임시 폴더 등)에서 돌리면 이 검사는 뜻이 없다.
   예전에는 그런 자리에서도 조용히 통과했다 — 그래서 목록에는 있는데 파일이 없는
   것을 못 잡았다(bgm_spring). 건너뛰는 것은 좋으나 **건너뛴다고 말은 해야 한다.** */
const HAVE_STATIC = fs.existsSync("static") && fs.readdirSync("static").some(f => f.endsWith(".mp3"));
if (!HAVE_STATIC) console.log("     ⚠ static/ 에 mp3 가 없어 파일 검사는 건너뜁니다 (전체 체크아웃에서 돌리세요)");
let tot = 0, sizes = [];
files.forEach((f) => {
  const p = path.join("static", f);
  const e = fs.existsSync(p);
  if (!HAVE_STATIC) return;
  ok("파일 있음 · " + f, e);
  if (e) { const kb = Math.round(fs.statSync(p).size / 1024); tot += kb; sizes.push(kb); }
});
ok("한 곡이 2.5MB 안쪽 (20명 동시 접속)", sizes.every(k => k < 2560), Math.max(...sizes) + "KB");
ok("옛 320kbps 원본을 그대로 안 쓴다", !files.includes("bgm.mp3"));
/* ★ v136 — 반대 방향도 본다. static/ 에 bgm_*.mp3 가 있는데 목록에 없으면
   **아무도 안 트는 파일**이 깃헙에 얹혀 다닌다. 반대로 목록에만 있으면
   그 곡이 걸릴 때 소리가 안 난다(v136에서 bgm_spring 이 그랬다 — 4곡 중 1곡, 25%).
   목록과 파일은 **한 벌**이어야 한다. */
if (HAVE_STATIC) {
  const onDisk = fs.readdirSync("static").filter(f => /^bgm_.*\.mp3$/.test(f)).sort();
  const listed = files.slice().sort();
  ok("목록과 파일이 한 벌이다", JSON.stringify(onDisk) === JSON.stringify(listed),
     `파일 ${onDisk.join(",")} / 목록 ${listed.join(",")}`);
}
// 판올림마다 숫자가 바뀐다 — 특정 숫자를 박아 두면 올릴 때마다 깨진다.
ok("?v= 로 옛 파일을 흘려보낸다", (L[1].match(/\?v=\d+/g) || []).length === files.length);
console.log("     (" + files.length + "곡 합계 " + tot + "KB · 한 사람은 그중 한 곡만 받는다)");

console.log("── ③ 접힌 페이더 대신 남는 한 줄 ──");
ok("자리가 있다", /<div class="style-line" id="styleLine" hidden>/.test(html));
ok("모양이 있다", /\.style-line \{/.test(html));
ok("그리는 함수가 있다", /function styleLinePaint\(/.test(html) && /function styleLineShow\(/.test(html));
ok("대화가 시작되면 띄운다", /faderSection\.classList\.add\("fader-collapsed"\);\s*\n\s*try \{ styleLineShow\(true\)/.test(html));
/* v115 — 홈으로 돌아갈 때도 거둔다. 페이더를 펼치는 두 곳 + goHome = 세 곳.
   (홈에서는 이 줄이 대화 화면 쪽에 있어 눈에 안 보이지만, 남겨 두면
    다른 길로 대화 화면에 들어갔을 때 지난 대화의 값이 그대로 보인다) */
ok("페이더를 펼치면 거둔다", (html.match(/styleLineShow\(false\)/g) || []).length === 3);
ok("홈으로 가도 거둔다", /styleLineShow\(false\)[^\n]*\n\s*setScreen\("home"\)/.test(html));
// v116 — 두 화자의 화계가 갈리면 둘을 나란히 보인다. 계산은 speechOf() 한 곳.
ok("말투 계산이 한 곳(speechOf)", (html.match(/function speechOf\(d, p\)/g) || []).length === 1
   && !/const avg = \(\+distSlider\.value \+ \+powerSlider\.value\) \/ 2/.test(html));
ok("비대칭이면 상대 화계도 보인다", /_mine === _theirs/.test(html) && /partnerSpeechOf/.test(html));
ok("대등한 지위는 말하지 않는다", /if \(pi !== 2\) parts\.push/.test(html));
ok("도움을 끄면 그 말도 없다", /scafSlider\.value > 0\) parts\.push\("🪜 "/.test(html));
ok("언어를 바꾸면 한 줄도 따라간다", /!_sl\.hidden\) styleLinePaint\(\)/.test(html));
ok("숫자(70 같은 것)를 다시 보이지 않는다", !/styleLinePaint[\s\S]{0,900}getDistLabel/.test(html));

console.log("── ④ 18개 언어가 자기 말을 갖췄는가 ──");
const a = html.indexOf("    const I18N = {");
const lastAsg = [...html.matchAll(/for \(const _\w+ in I18N_\w+\) \{[^\n]*\n/g)].pop();
const I = new Function(html.slice(a, lastAsg.index + lastAsg[0].length) + "\nreturn I18N;")();
const langs = Object.keys(I);
ok("사전이 18개 언어", langs.length === 18, langs.length + "개");
["sumFormal", "sumPolite", "sumCasual", "distLv", "powerLv", "scaf3"].forEach((k) =>
  ok("모든 언어에 " + k, langs.every(g => I[g][k] !== undefined)));
const dLv = v => (v <= 15 ? 0 : v <= 35 ? 1 : v <= 65 ? 2 : v <= 85 ? 3 : 4);
const tier = (d, p) => { const lv = dLv((d + p) / 2); return lv <= 1 ? 0 : (lv <= 3 ? 1 : 2); };
const SUM = ["sumFormal", "sumPolite", "sumCasual"];
const line = (g, d, p, sc) => { const L = I[g], P = [L.distLv[dLv(d)]];
  if (dLv(p) !== 2) P.push(L.powerLv[dLv(p)]);
  if (sc > 0) P.push("🪜 " + L["scaf" + sc]);
  P.push(L[SUM[tier(d, p)]]); return P.join(" · "); };
// 여섯 언어(ne·lo·my·km·uk·ky)는 I18N_X6 가 ko+en 으로 새로 만든다 → 영어가 새어 나오기 쉽다
const leak = langs.filter(g => g !== "en" && /Strangers|Acquaintances|Close|Best friends|Junior|Equal|Slightly/.test(line(g, 70, 50, 2)));
ok("영어가 새어 나오는 언어 없음", leak.length === 0, leak.join(","));
ok("눈금 패치가 I18N_X6 뒤에 있다", html.indexOf("I18N_X6[_l]) }") < html.indexOf("const I18N_LV6")
                                  || html.indexOf("I18N_X6[_l]); }") < html.indexOf("const I18N_LV6"));
const longest = Math.max(...langs.map(g => line(g, 10, 20, 3).length));
ok("가장 긴 줄도 90자 안쪽 (휴대폰 두 줄)", longest <= 90, longest + "자");
ok("말투에 '화계' 같은 용어가 없다", !langs.some(g => SUM.some(k => /화계|speech level|honorific system/i.test(I[g][k]))));
console.log("     예) " + line("ko", 70, 50, 2));
console.log("     예) " + line("ko", 95, 90, 3));

console.log(bad ? `\n💥 ${bad}건` : "\n🎉 소리·요약 한 줄 이상 없음");
process.exit(bad ? 1 : 0);
