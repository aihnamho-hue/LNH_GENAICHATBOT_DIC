// 학습자 모국어(12개) 번역 완전성 검사
const fs=require("fs"), vm=require("vm");
const SRC=process.argv[2]||require("path").join(__dirname,"templates","index.html");
const html=fs.readFileSync(SRC,"utf8");
const script=html.match(/<script>([\s\S]*)<\/script>/)[1];

// I18N 선언부 + 병합 루프 전부를 잘라내 실행한다 (마지막 Object.assign 줄까지)
const start=script.indexOf("const I18N = {");
let last=-1, re=/for \(const _l(?:ng)? in I18N_[A-Z0-9]+\) \{[^\n]*\n/g, m;
while((m=re.exec(script))) last=m.index+m[0].length;
if(start<0||last<0){ console.log("❌ I18N 블록을 못 찾음"); process.exit(1); }
const chunk=script.slice(start,last);
const ctx={console};
vm.createContext(ctx);
try { vm.runInContext(chunk+"\n;globalThis.__I18N=I18N;", ctx); }
catch(e){ console.log("❌ I18N 블록 실행 실패:", e.message); process.exit(1); }
const I18N=ctx.__I18N;
// vcSample 은 학습자가 들어야 할 '한국어 예시 발화'라 모든 언어에서 한국어가 정상이다
const KO_ON_PURPOSE=new Set(["vcSample"]);

const LANGS=["ko","en","zh","ja","vi","th","id","mn","uz","ru","es","fr"];
const NAMES={ko:"한국어",en:"영어",zh:"중국어",ja:"일본어",vi:"베트남어",th:"태국어",id:"인도네시아어",mn:"몽골어",uz:"우즈베크어",ru:"러시아어",es:"스페인어",fr:"프랑스어"};
let fail=0;

console.log("── ① 언어 12개가 모두 있는가 ──");
const missingLang=LANGS.filter(l=>!I18N[l]);
console.log(missingLang.length? "  ❌ 빠진 언어: "+missingLang.join(", ") : `  ✅ 12개 언어 모두 존재 (${Object.keys(I18N).length}개 등록)`);
if(missingLang.length) fail++;

console.log("\n── ② 한국어에 있는 키가 다른 언어에도 있는가 ──");
const koKeys=Object.keys(I18N.ko).sort();
console.log(`  기준: 한국어 ${koKeys.length}개 키`);
let holes=0;
for(const l of LANGS){
  if(l==="ko"||!I18N[l]) continue;
  const miss=koKeys.filter(k=>!(k in I18N[l]));
  if(miss.length){
    holes+=miss.length; fail++;
    console.log(`  ❌ ${NAMES[l]}(${l}) — ${miss.length}개 누락: ${miss.slice(0,10).join(", ")}${miss.length>10?" …":""}`);
  } else console.log(`  ✅ ${NAMES[l]}(${l}) — 완전`);
}

console.log("\n── ③ 한국어 원문이 그대로 남은 곳 (번역 누락 의심) ──");
const hangul=/[가-힣]/;
let raw=0;
for(const l of LANGS){
  if(l==="ko"||!I18N[l]) continue;
  const same=koKeys.filter(k=>{
    const a=I18N.ko[k], b=I18N[l][k];
    return !KO_ON_PURPOSE.has(k) && typeof a==="string" && typeof b==="string" && a===b && hangul.test(a) && a.replace(/[^가-힣]/g,"").length>1;
  });
  if(same.length){ raw+=same.length; console.log(`  ⚠️ ${NAMES[l]}(${l}) — ${same.length}개가 한국어 그대로: ${same.slice(0,6).join(", ")}${same.length>6?" …":""}`); }
}
if(!raw) console.log("  ✅ 없음");

console.log("\n── ④ 코드가 부르는 키가 사전에 있는가 ──");
const used=new Set([...script.matchAll(/\bt\(\s*"([a-zA-Z0-9_]+)"/g)].map(m=>m[1]));
const undef=[...used].filter(k=>!(k in I18N.ko));
console.log(`  t("...") 호출 ${used.size}종`);
if(undef.length){ fail++; console.log("  ❌ 사전에 없는 키: "+undef.join(", ")); }
else console.log("  ✅ 전부 정의됨");

console.log("\n── ⑤ 아무 데서도 안 쓰는 키 ──");
// data-qkey 처럼 t(변수)로 부르는 키는 HTML의 data-* 값에서 찾는다
const dyn=new Set([...html.matchAll(/data-(?:qkey|i18n)="([A-Za-z0-9_]+)"/g)].map(m=>m[1]));
const unused=koKeys.filter(k=>!used.has(k) && !dyn.has(k));
console.log(unused.length? `  ℹ️ ${unused.length}개: ${unused.slice(0,14).join(", ")}${unused.length>14?" …":""}` : "  ✅ 없음");

console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모국어 패치 이상 없음");
process.exit(fail?1:0);
