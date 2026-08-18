const fs = require("fs"); const { JSDOM } = require("jsdom");
const html = fs.readFileSync("i.html", "utf8");

function boot(url, opts = {}) {
  const errs = [];
  const dom = new JSDOM(html, { runScripts: "dangerously", url, pretendToBeVisual: true,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: !!opts.standalone, addListener(){}, removeListener(){}, addEventListener(){}, removeEventListener(){} });
      if (opts.ua) Object.defineProperty(w.navigator, "userAgent", { value: opts.ua, configurable: true });
      w.HTMLMediaElement.prototype.play = () => Promise.resolve();
      w.fetch = (u) => {
        if (String(u).indexOf("/app-info") > -1)
          return Promise.resolve({ json: () => Promise.resolve(opts.apk ? { apk: "/download/hoarang.apk", size: 1234 } : { apk: "" }) });
        return Promise.reject(new Error("no net"));
      };
      w.onerror = (m) => errs.push(String(m));
    }});
  dom.window.addEventListener("error", e => errs.push(String(e.message)));
  return { d: dom.window.document, w: dom.window, errs, tick: () => new Promise(r => setTimeout(r, 30)) };
}
function vis(el) { return el && !el.classList.contains("hidden") && !el.hidden; }
let fail = 0;
function ok(name, cond) { console.log((cond ? "  ✅ " : "  ❌ ") + name); if (!cond) fail++; }

console.log("① 일반 브라우저 첫 방문 — 관문이 뜨고 나라 선택이 먼저");
{
  const { d, errs } = boot("https://korean-dic.onrender.com/");
  ok("로드 오류 없음", errs.length === 0);
  ok("관문 표시됨", vis(d.getElementById("installGate")));
  ok("① 나라 선택 표시", vis(d.getElementById("igStep1")));
  ok("② 설치 안내 숨김", !vis(d.getElementById("igStep2")));
  ok("'웹에서 그냥 볼게요' 버튼 없음", d.getElementById("igSkipBtn") === null);

  d.querySelector('[data-iglang="vi"]').click();
  ok("베트남어 고르면 ②로", vis(d.getElementById("igStep2")) && !vis(d.getElementById("igStep1")));
  ok("제목이 베트남어", d.getElementById("igTitleEl").textContent === "Cài ứng dụng để bắt đầu");
  ok("관문은 여전히 닫히지 않음", vis(d.getElementById("installGate")));
  ok("언어 다시 고르기 있음", d.getElementById("igLangBackBtn").textContent.length > 0);
}

console.log("② 아이폰 사파리 — 공유 → 홈 화면에 추가 안내");
{
  const { d } = boot("https://korean-dic.onrender.com/", { ua: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1" });
  d.querySelector('[data-iglang="ko"]').click();
  ok("아이폰 순서 안내", d.getElementById("igStepsEl").textContent.includes("공유"));
  ok("복사 버튼 숨김", d.getElementById("igCopyBtn").hidden);
}

console.log("③ 카카오톡 인앱 — 크롬에서 열기");
{
  const { d } = boot("https://korean-dic.onrender.com/", { ua: "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36 KAKAOTALK" });
  d.querySelector('[data-iglang="en"]').click();
  ok("버튼이 'Open in Chrome'", d.getElementById("igInstallBtn").textContent === "Open in Chrome");
  ok("동작 = chrome", d.getElementById("igInstallBtn").dataset.act === "chrome");
}

console.log("④ 앱으로 실행 중(standalone) — 관문 없음");
{
  const { d } = boot("https://korean-dic.onrender.com/?src=app", { standalone: true });
  ok("관문 숨김", !vis(d.getElementById("installGate")));
}

console.log("⑤ '웹에서 그냥 볼게요' — 관문을 닫고 웹으로 쓸 수 있다");
{
  const { d } = boot("https://korean-dic.onrender.com/");
  d.querySelector('[data-iglang="ko"]').click();
  ok("웹으로 계속 버튼이 있다", !!d.getElementById("igWebBtn"));
  d.getElementById("igWebBtn").click();
  ok("관문이 닫힌다", !vis(d.getElementById("installGate")));
  ok("숨은 ?web=1 우회는 없앴다", !/TEACHER_WEB/.test(require("fs").readFileSync("i.html","utf8")));
}

const AOS = "Mozilla/5.0 (Linux; Android 13; SM-S911N) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36";

(async () => {
console.log("⑥ 안드로이드 + 서버에 APK 있음 — 앱 파일을 준다");
{
  const { d, tick } = boot("https://korean-dic.onrender.com/", { ua: AOS, apk: true });
  d.querySelector('[data-iglang="ko"]').click();
  await tick();
  ok("버튼이 '앱 파일 받기'", d.getElementById("igInstallBtn").textContent === "앱 파일 받기");
  ok("동작 = apk", d.getElementById("igInstallBtn").dataset.act === "apk");
  ok("3단계 안내 표시", d.getElementById("igStepsEl").textContent.includes("앱 파일을 받으세요"));
  ok("'안전해요' 안내 보임", !d.getElementById("igSafeEl").hidden);
}

console.log("⑦ 안드로이드지만 APK 미업로드 — PWA 안내로 되돌아감");
{
  const { d, tick } = boot("https://korean-dic.onrender.com/", { ua: AOS, apk: false });
  d.querySelector('[data-iglang="ko"]').click();
  await tick();
  ok("동작이 apk가 아님", d.getElementById("igInstallBtn").dataset.act !== "apk");
  ok("'안전해요' 숨김", d.getElementById("igSafeEl").hidden);
}

console.log("⑧ APK로 실행 중(TWA) — 관문 없음");
{
  const { d } = boot("https://korean-dic.onrender.com/?src=twa", { ua: AOS, apk: true });
  ok("관문 숨김", !vis(d.getElementById("installGate")));
}

console.log("⑨ 아이폰은 APK가 있어도 홈 화면 추가 안내");
{
  const { d, tick } = boot("https://korean-dic.onrender.com/", { ua: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1", apk: true });
  d.querySelector('[data-iglang="ko"]').click();
  await tick();
  ok("공유 안내 유지", d.getElementById("igStepsEl").textContent.includes("공유"));
  ok("동작 = hint", d.getElementById("igInstallBtn").dataset.act === "hint");
}

console.log(fail === 0 ? "\n🎉 모두 통과" : `\n💥 실패 ${fail}건`);
process.exit(fail ? 1 : 0);
})();
