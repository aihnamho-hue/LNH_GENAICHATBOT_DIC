/* prtest.js — 발화 연습의 두 가지를 못 박아 둔다 (v112)
   ① 문이 열리는 동안은 첫 발화가 나오지 않는다
   ② 말하기는 '꾹 눌러 말하기' 하나뿐이다 (온·오프 토글이 아니다)
   이 둘은 실기기 시험에서 학습자가 직접 걸려 넘어진 자리다. */
const fs = require("fs");
const html = fs.readFileSync("app.html", "utf8");
let bad = 0;
const ok = (t, c) => { console.log((c ? "  ✅ " : "  ❌ ") + t); if (!c) bad++; };

console.log("── ① 문이 열린 뒤에 말한다 ──");
ok("문 열림 예약 장치가 있다",           /function doorOnOpen\(/.test(html) && /function doorFireOpen\(/.test(html));
ok("여는 문일 때만 예약이 걸린다",        /if \(mode === "opening"\) doorAfter\(DOOR_VOICE_MS, doorFireOpen\)/.test(html));
const ms = (html.match(/const DOOR_VOICE_MS = (\d+)/) || [])[1];
ok("문틈이 벌어진 뒤다 (1.92초 이후)",    Number(ms) >= 1920);
ok("문이 다 열리기 전이다 (3.2초 이내)",  Number(ms) <= 3200);
ok("문을 눌러 건너뛰면 바로 말한다",      /swallowNextClick[\s\S]{0,220}doorFireOpen\(\)/.test(html));
ok("문을 치울 때도 예약을 흘려보낸다",    /clearDoorTimers\(\);\s*\n\s*try \{ doorFireOpen\(\)/.test(html));
ok("첫 연습은 소리 없이 그린다",          /openPractice\._doorShown = true;[\s\S]{0,700}renderPractice\(false\);[\s\S]{0,300}doorOnOpen\(/.test(html));
ok("창을 닫았으면 말하지 않는다",         /doorOnOpen\(\(\) => \{[\s\S]{0,200}prOverlay\.classList\.contains\("hidden"\)\) return;/.test(html));

console.log("── ② 꾹 눌러 말하기 하나로 ──");
ok("탭 토글 흔적이 없다",                 !/prTapMode/.test(html) && !/PR_TAP_MS/.test(html));
ok("누르면 시작하는 함수가 있다",         /function prRecStart\(/.test(html));
ok("떼면 끝내는 함수가 있다",             /function prRecStop\(/.test(html));
ok("떼면 꼬리를 두고 끊는다",             /prTailTimer = setTimeout\([\s\S]{0,120}prRecStop\(\)/.test(html));
ok("꼬리 대기 중 다시 누르면 이어간다",   /if \(prTailTimer\) \{[\s\S]{0,200}clearTimeout\(prTailTimer\)/.test(html));
// 대화 화면 발화 버튼이 가진 안전장치를 그대로 갖췄는가
["lostpointercapture", "blur", "visibilitychange"].forEach((ev) => {
  const re = new RegExp('addEventListener\\("' + ev + '"[\\s\\S]{0,140}prHoldEnd');
  ok("안전장치 · " + ev, re.test(html));
});
ok("창 밖에서 떼도 끝난다",               /window\.addEventListener\("pointerup", \(\) => \{ if \(prHeld\) prHoldEnd\(\); \}\)/.test(html));
ok("스페이스바로도 꾹 누른다",            /e\.code !== "Space"[\s\S]{0,300}prHoldStart\(\)/.test(html));

console.log("── ③ 두 버튼이 같아 보이는가 ──");
ok("연습 버튼도 아이콘↔막대를 바꾼다",    /\.pr-mic\.talking \.ptt-mic \{ display: none/.test(html)
                                        && /\.pr-mic\.talking \.ptt-vu \{ display: flex/.test(html));
ok("연습 버튼 속도 [아이콘+막대+글자]",   /function prBuildMic\(/.test(html) && /prVuBars\.push\(b\)/.test(html));
ok("글자만 갈아 끼운다 (아이콘 안 지운다)", !/prMicBtn\.textContent = stripLeadEmoji/.test(html));
ok("막대가 실제 목소리로 움직인다",       /getFloatTimeDomainData/.test(html));
ok("막대 구간이 대화 화면과 같다",        (html.match(/\(rms - 0\.015\) \/ 0\.22/) || []).length === 1
                                        && /\(vuLevel - 0\.015\) \/ 0\.22/.test(html));
ok("막대 소리는 스피커로 안 나간다",      !/prVuAn\.connect\(prVuCtx\.destination\)/.test(html));

console.log("── ④ 허락 팝업 사이에 손을 떼는 경우 ──");
ok("켜는 중에는 두 번 켜지 않는다",       /if \(prRecOn \|\| prStarting\) return;/.test(html));
ok("켜고 나서 안 누르고 있으면 끝낸다",   /if \(!prHeld\) prHoldEnd\(\);/.test(html));
ok("실패해도 켜는 중 표시를 푼다",        (html.match(/prStarting = false;/g) || []).length >= 3);

console.log("── ⑤ 안내 문구가 동작과 맞는가 ──");
const rec = [...html.matchAll(/prMicRec:"([^"]*)"/g)].map(m => m[1]);
ok("prMicRec 18개 언어",                  rec.length === 18);
ok("'다시 누르라'는 말이 남아 있지 않다", !rec.some(x => /다시 누르|tap again|もう一度押|再点一次|нажмите ещё раз|дахин дарна|yana bosing|फेरि थिच|ຄົດອີກ|ထပ်နှိပ်|ម្តងទៀត|de nuevo al terminar|à nouveau quand|lần nữa|lagi jika selesai|แตะอีกครั้ง|кайра басы/.test(x)));
ok("마이크 없는 기기용 단추는 남아 있다", /prSaidBtn/.test(html) && /prSaidIt:"/.test(html));

console.log(bad ? `\n💥 ${bad}건` : "\n🎉 발화 연습 이상 없음");
process.exit(bad ? 1 : 0);
