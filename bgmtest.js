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
/* ★ v122 — 「다섯 곡」을 박아 두었더니 곡 하나를 빼자 깨졌다.
   재야 할 것은 곡의 개수가 아니라 「여러 곡 가운데 하나를 꽂는가」다. */
ok("여러 곡 중 하나를 꽂는다", (html.match(/\/static\/bgm_[a-z]+\.mp3/g) || []).length >= 3);
ok("꽂은 뒤 load\(\) 를 부른다", /bgm\.setAttribute\("src"[\s\S]{0,900}?bgm\.load\(\)/.test(html));
ok("캐시버스터가 판올림을 따라간다", !/bgm_[a-z]+\.mp3\?v=11[0-5]/.test(html));

console.log("── 경어법: 두 축을 따로 ──");
ok("평균식이 사라졌다", !/const avg = \(\+distSlider\.value \+ \+powerSlider\.value\) \/ 2/.test(html));
ok("계산이 한 곳", (html.match(/function speechOf\(d, p\)/g) || []).length === 1);
ok("상대의 말투도 센다", /function partnerSpeechOf/.test(html));
/* ★★ v136 — 여기 **코드 한 줄을 통째로 베껴** 두고 있었다.
     `if (d >= SPEECH_CLOSE) return p >= 45 ? 2 : 1;` 를 글자 그대로 찾고 있었으니,
     v134에서 눈금을 고치자(45→35, 70→65) 그대로 깨졌다.
     베낀 검사는 원본이 바뀌면 같이 안 바뀐다 — **검사가 거짓말을 한다.**
     (같은 병을 v134에서 셋, 여기까지 다섯 번째로 만났다)
   → 글자를 찾지 말고 **돌려서 결과를 본다.** 무엇을 지키려던 것이었나:
       ㄱ) 반말은 가까운 사이에서만 나온다
       ㄴ) 낯선 사이·대등은 합쇼체다
     이 둘은 논문 〈표 4-x〉의 원칙이고, 눈금이 바뀌어도 변하지 않는다. */
{
    const src = /const SPEECH_FAR[\s\S]*?\n    \}\n    function partnerSpeechOf[\s\S]*?\n    \}/.exec(html);
    ok("화계 함수를 떼어 올 수 있다", !!src);
    if (src) {
        const f = new Function(src[0] + "; return {speechOf, partnerSpeechOf};")();
        const far = [];   // 안 가까운 사이(친밀도 0~65)에서 반말이 나오는가
        for (let dd = 0; dd <= 65; dd++) for (let pp = 0; pp <= 100; pp++)
            if (f.speechOf(dd, pp) === 2 || f.partnerSpeechOf(dd, pp) === 2) far.push([dd, pp]);
        ok("반말은 가까울 때만", far.length === 0, far.slice(0, 3));
        ok("낯선 사이·대등은 합쇼체", f.speechOf(10, 50) === 0 && f.partnerSpeechOf(10, 50) === 0,
           [f.speechOf(10, 50), f.partnerSpeechOf(10, 50)]);
        // v134에서 고친 것 — 「아는 사이」에서 지위가 실제로 일을 하는가
        ok("아는 사이에서 지위가 화계를 가른다",
           new Set([10, 50, 90].map((pp) => f.speechOf(25, pp))).size >= 2,
           [10, 50, 90].map((pp) => f.speechOf(25, pp)));
    }
}
ok("비대칭을 한 줄에 보인다", /_mine === _theirs/.test(html) && /sumMineCasual/.test(html));
ok("비대칭 문구가 18개 언어", (html.match(/sumMineFormal:"/g) || []).length === 18);

console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail ? 1 : 0);
