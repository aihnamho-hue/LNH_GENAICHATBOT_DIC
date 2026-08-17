/* sndtest.js — 소리와 '접힌 페이더 한 줄' (v113)
   ① 음량 15% · 나머지도 같은 비율
   ② 홈 배경음 무작위 다섯 곡 — 파일이 다 있고 크기가 고르며 무겁지 않은가
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
ok("다섯 곡이 목록에 있다", files.length === 5, files.join(" "));
ok("무작위로 고른다", /HOME_BGM\[Math\.floor\(Math\.random\(\) \* HOME_BGM\.length\)\]/.test(html));
ok("src 를 비워 두고 고른 하나만 받는다", /<audio id="bgm" loop preload="none">/.test(html));
let tot = 0, sizes = [];
files.forEach((f) => {
  const p = path.join("static", f);
  const e = fs.existsSync(p);
  ok("파일 있음 · " + f, e);
  if (e) { const kb = Math.round(fs.statSync(p).size / 1024); tot += kb; sizes.push(kb); }
});
ok("한 곡이 2.5MB 안쪽 (20명 동시 접속)", sizes.every(k => k < 2560), Math.max(...sizes) + "KB");
ok("옛 320kbps 원본을 그대로 안 쓴다", !files.includes("bgm.mp3"));
ok("?v= 로 옛 파일을 흘려보낸다", (L[1].match(/\?v=113/g) || []).length === 5);
console.log("     (다섯 곡 합계 " + tot + "KB · 한 사람은 그중 한 곡만 받는다)");

console.log("── ③ 접힌 페이더 대신 남는 한 줄 ──");
ok("자리가 있다", /<div class="style-line" id="styleLine" hidden>/.test(html));
ok("모양이 있다", /\.style-line \{/.test(html));
ok("그리는 함수가 있다", /function styleLinePaint\(/.test(html) && /function styleLineShow\(/.test(html));
ok("대화가 시작되면 띄운다", /faderSection\.classList\.add\("fader-collapsed"\);\s*\n\s*try \{ styleLineShow\(true\)/.test(html));
ok("페이더를 펼치면 거둔다", (html.match(/styleLineShow\(false\)/g) || []).length === 2);
ok("말투는 speechTier() 한 곳만 본다", /\["sumFormal", "sumPolite", "sumCasual"\]\[speechTier\(\)\]/.test(html)
                                     && (html.match(/function speechTier\(/g) || []).length === 1);
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
