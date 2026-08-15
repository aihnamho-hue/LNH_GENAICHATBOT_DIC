/* v90 — 설치 안내: 언어 먼저 → 단계 카드 → 화살표 (아이폰·안드로이드·인앱) */
const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2] || "app.html", "utf8");
let fail = 0;
const ok = (m, c) => { console.log("  " + (c ? "✅" : "❌") + " " + m); if (!c) fail++; };

const UA = {
  iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  android: "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
  samsung: "Mozilla/5.0 (Linux; Android 13; SM-A536N) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/115.0.0.0 Mobile Safari/537.36",
};
UA.kakaoIos = UA.iphone + " KAKAOTALK 10.5.0";
UA.kakaoAos = UA.android + " KAKAOTALK 10.5.0";

function boot(ua, opts, done) {
  const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true,
    url: "https://korean-dic.onrender.com/",
    beforeParse(w) {
      Object.defineProperty(w.navigator, "userAgent", { value: ua, configurable: true });
      Object.defineProperty(w.navigator, "language", { value: opts.lang || "ko-KR", configurable: true });
      w.HTMLMediaElement.prototype.play = () => Promise.resolve();
      w.HTMLMediaElement.prototype.pause = () => {};
      w.fetch = () => Promise.reject(new Error("no net"));
      w.Element.prototype.scrollIntoView = () => {};
      if (opts.prompt) {
        w.addEventListener("load", () => {
          const e = new w.Event("beforeinstallprompt");
          e.prompt = () => Promise.resolve();
          e.userChoice = Promise.resolve({ outcome: "accepted" });
          w.dispatchEvent(e);
        });
      }
    } });
  setTimeout(() => done(dom.window.document, dom.window), opts.prompt ? 700 : 550);
}
const cards = (d, sel) => [...d.querySelectorAll(sel + " .ig-step")];
const pickLang = (d, sel, code) => { const b = d.querySelector(`${sel} [data-${code}]`); if (b) b.click(); };

console.log("── ① 아이폰 · 사파리 ──");
boot(UA.iphone, {}, (d) => {
  ok("언어부터 묻는다", !d.getElementById("igStep1").hidden && d.getElementById("igStep2").hidden);
  d.querySelector('#igStep1 [data-iglang="vi"]').click();
  ok("고른 말로 안내가 바뀐다", d.getElementById("igTitleEl").textContent.includes("ứng dụng"));
  const c = cards(d, "#igStepsEl");
  ok(`단계 카드 ${c.length}장`, c.length === 3);
  ok("첫 카드는 공유 그림", c[0].querySelector("use").getAttribute("href") === "#ic-share");
  const pt = d.getElementById("igPointEl");
  ok("아래를 가리키는 화살표", !pt.classList.contains("hidden") && pt.querySelector(".arw").textContent === "↓");
  d.getElementById("igInstallBtn").click();
  ok("공유 창 그림이 뜬다", !d.getElementById("igShot").hidden);
  ok("찾을 줄이 강조된다", (d.querySelector("#igShot .row.hit").textContent || "").includes("MH chính"));

  console.log("── ② 안드로이드 · 크롬 (설치 버튼이 오는 경우) ──");
  boot(UA.android, { prompt: true }, (d2) => {
    d2.querySelector('#igStep1 [data-iglang="ko"]').click();
    const b = d2.getElementById("igInstallBtn");
    ok("한 번에 설치하는 버튼", b.dataset.act === "install" && b.textContent.includes("지금 설치"));
    const c2 = cards(d2, "#igStepsEl");
    ok(`단계 카드 ${c2.length}장`, c2.length === 3);
    ok("⋮ 그림으로 시작", c2[0].querySelector("use").getAttribute("href") === "#ic-dots");
    ok("설치 버튼이 있으면 화살표는 안 띄운다", d2.getElementById("igPointEl").classList.contains("hidden"));

    console.log("── ③ 안드로이드 · 설치 버튼이 안 오는 경우 ──");
    boot(UA.samsung, {}, (d3) => {
      d3.querySelector('#igStep1 [data-iglang="ko"]').click();
      const c3 = cards(d3, "#igStepsEl");
      ok(`단계 카드 ${c3.length}장`, c3.length === 3);
      const pt3 = d3.getElementById("igPointEl");
      ok("오른쪽 위를 가리킨다", !pt3.classList.contains("hidden")
         && pt3.classList.contains("top") && pt3.querySelector(".arw").textContent === "↑");
      ok("안내가 ⋮ 로 시작", c3[0].querySelector(".tx").textContent.includes("⋮"));
      ok("⋮ 그림", c3[0].querySelector("use").getAttribute("href") === "#ic-dots");
      ok("크롬으로 여는 길도 남긴다", !d3.getElementById("igCopyBtn").hidden);

      console.log("── ④ 카카오톡 (아이폰) ──");
      boot(UA.kakaoIos, { lang: "vi-VN" }, (d4) => {
        ok("인앱 관문이 뜬다", !d4.getElementById("inappGate").classList.contains("hidden"));
        ok("★ 언어부터 묻는다", !d4.getElementById("iaStep1").hidden && d4.getElementById("iaStep2").hidden);
        ok("기기 언어로 넘겨짚지 않는다", cards(d4, "#inappStepsEl").length === 0);
        d4.querySelector('#iaStep1 [data-ialang="th"]').click();
        ok("고른 말로 안내가 나온다", d4.getElementById("inappTitleEl").textContent.includes("เบราว์เซอร์"));
        ok(`인앱 안내도 카드 ${cards(d4, "#inappStepsEl").length}장`, cards(d4, "#inappStepsEl").length === 3);

        console.log("── ⑤ 카카오톡 (안드로이드) ──");
        boot(UA.kakaoAos, {}, (d5) => {
          ok("인앱 관문이 뜬다", !d5.getElementById("inappGate").classList.contains("hidden"));
          ok("언어부터 묻는다", !d5.getElementById("iaStep1").hidden);
          d5.querySelector('#iaStep1 [data-ialang="ko"]').click();
          ok("'브라우저로 열기' 버튼", d5.getElementById("inappOpenBtn").textContent.includes("브라우저"));
          ok(`카드 ${cards(d5, "#inappStepsEl").length}장`, cards(d5, "#inappStepsEl").length === 3);

          console.log("── ⑥ 한 번 고른 언어는 기억한다 ──");
          const dom6 = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true,
            url: "https://korean-dic.onrender.com/",
            beforeParse(w) {
              Object.defineProperty(w.navigator, "userAgent", { value: UA.android, configurable: true });
              w.localStorage.setItem("uiLang", "ru");
              w.HTMLMediaElement.prototype.play = () => Promise.resolve();
              w.HTMLMediaElement.prototype.pause = () => {};
              w.fetch = () => Promise.reject(new Error("no net"));
              w.Element.prototype.scrollIntoView = () => {};
            } });
          setTimeout(() => {
            const d6 = dom6.window.document;
            ok("다시 묻지 않고 바로 안내로", d6.getElementById("igStep1").hidden && !d6.getElementById("igStep2").hidden);
            ok("기억한 말로 나온다", d6.getElementById("igTitleEl").textContent.includes("приложение"));
            console.log(fail ? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
            process.exit(fail ? 1 : 0);
          }, 550);
        });
      });
    });
  });
});
