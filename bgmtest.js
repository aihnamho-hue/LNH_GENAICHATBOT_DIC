/* v116 — 배경음이 PC·안드로이드에서도 나는가 (그래프에 물린 뒤 el.volume 문제) */
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

console.log("── 그래프에 물린 뒤의 음량 ──");
ok("연결한 요소는 el.volume 을 1로 되돌린다",
   /el\.dataset\.wired = "1";[\s\S]{0,700}?try \{ el\.volume = 1; \} catch/.test(html));
ok("fadeIn 이 물린 요소의 volume 을 0으로 안 내린다",
   /if \(el\.paused && !bgmGain\.has\(el\)\) \{ try \{ el\.volume = 0/.test(html));
ok("음량은 GainNode 로 준다", /g\.gain\.linearRampToValueAtTime/.test(html));
ok("첫 터치에 잠금을 푼다", /document\.addEventListener\("pointerdown", unlockBgm\)/.test(html));
ok("다섯 곡 중 하나를 꽂는다", (html.match(/\/static\/bgm_[a-z]+\.mp3/g) || []).length === 5);
ok("꽂은 뒤 load\(\) 를 부른다", /bgm\.setAttribute\("src"[\s\S]{0,900}?bgm\.load\(\)/.test(html));
ok("캐시버스터가 판올림을 따라간다", !/bgm_[a-z]+\.mp3\?v=11[0-5]/.test(html));

console.log("── 경어법: 두 축을 따로 ──");
ok("평균식이 사라졌다", !/const avg = \(\+distSlider\.value \+ \+powerSlider\.value\) \/ 2/.test(html));
ok("계산이 한 곳", (html.match(/function speechOf\(d, p\)/g) || []).length === 1);
ok("상대의 말투도 센다", /function partnerSpeechOf/.test(html));
ok("반말은 가까울 때만", /if \(d >= SPEECH_CLOSE\) return p >= 45 \? 2 : 1;/.test(html));
ok("낯선 사이는 격식체", /if \(d <= SPEECH_FAR\) return p >= 70 \? 1 : 0;/.test(html));
ok("비대칭을 한 줄에 보인다", /_mine === _theirs/.test(html) && /sumMineCasual/.test(html));
ok("비대칭 문구가 18개 언어", (html.match(/sumMineFormal:"/g) || []).length === 18);

console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail ? 1 : 0);
