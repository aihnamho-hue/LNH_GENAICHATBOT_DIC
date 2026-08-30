// JS가 찾는 id / 클래스가 HTML에 실제로 있는지 — vuBars·homeBubble 사고 유형 예방
const fs=require("fs"), {JSDOM}=require("jsdom");
const SRC=process.argv[2]||require("path").join(__dirname,"templates","index.html");
const html=fs.readFileSync(SRC,"utf8");
const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const d=new JSDOM(html.replace(/<script>[\s\S]*?<\/script>/g,"")).window.document;
let fail=0;

// ① getElementById("x") 대상이 HTML에 있는가
const ids=new Set([...script.matchAll(/getElementById\(\s*"([A-Za-z0-9_\-]+)"\s*\)/g)].map(m=>m[1]));
/* ★ v129 — 코드가 만들어 붙이는 자리는 HTML 에 없는 것이 정상이다.
   (id 를 지어 넣고 곧바로 찾는 꼴 — createElement 뒤 .id = "..." 가 있으면 만든 것이다) */
const MADE = new Set([...script.matchAll(/\.id\s*=\s*"([A-Za-z0-9_\-]+)"/g)].map(m => m[1]));
const deadIds=[...ids].filter(i=>!d.getElementById(i) && !MADE.has(i));
if (MADE.size) console.log(`   (코드가 만들어 붙이는 자리 ${MADE.size}개는 뺐다)`);
console.log(`① getElementById 대상 ${ids.size}개`);
if(deadIds.length){fail++;console.log("  ❌ HTML에 없는 id: "+deadIds.join(", "));}
else console.log("  ✅ 전부 존재");

// ② querySelector('#id') 대상
const qids=new Set([...script.matchAll(/querySelector\(\s*["'`]#([A-Za-z0-9_\-]+)/g)].map(m=>m[1]));
const deadQ=[...qids].filter(i=>!d.getElementById(i));
console.log(`② querySelector('#…') 대상 ${qids.size}개`);
if(deadQ.length){fail++;console.log("  ❌ 없는 id: "+deadQ.join(", "));}
else console.log("  ✅ 전부 존재");

// ③ 자주 쓰는 클래스 선택자가 HTML/CSS에 있는가
const css=html.match(/<style>([\s\S]*?)<\/style>/)[1];
const cls=new Set([...script.matchAll(/querySelectorAll?\(\s*["'`]\.([a-z][a-z0-9\-]+)["'`\s,)]/g)].map(m=>m[1]));
const deadCls=[...cls].filter(c=>!d.querySelector("."+c) && !new RegExp("\\."+c+"[\\s{.,:]").test(css));
console.log(`③ querySelector('.…') 대상 ${cls.size}개`);
if(deadCls.length) console.log("  ⚠️ HTML·CSS 어디에도 없음: "+deadCls.join(", "));
else console.log("  ✅ 전부 존재");

// ④ HTML의 id 중 JS도 CSS도 안 쓰는 것 (죽은 마크업)
const allIds=[...d.querySelectorAll("[id]")].map(e=>e.id);
// <use href="#ic-…"> 로 쓰는 SVG 심볼도 '쓰임'으로 인정
const hrefIds=new Set([...html.matchAll(/href="#([A-Za-z0-9_\-]+)"/g)].map(m=>m[1]));
const orphan=allIds.filter(i=>!ids.has(i)&&!qids.has(i)&&!hrefIds.has(i)&&!new RegExp("#"+i+"[\\s{.,:\\[)]").test(css)&&!script.includes(`"${i}"`));
console.log(`④ HTML의 id ${allIds.length}개`);
console.log(orphan.length? "  ℹ️ 아무도 안 쓰는 id: "+orphan.slice(0,12).join(", ")+(orphan.length>12?" …":"") : "  ✅ 모두 쓰임");

// ⑤ addEventListener 를 거는 변수가 null일 수 있는지 (선언 즉시 접근)
const risky=[...script.matchAll(/document\.getElementById\("([A-Za-z0-9_]+)"\)\.addEventListener/g)].map(m=>m[1]).filter(i=>!d.getElementById(i));
console.log("⑤ 즉시 addEventListener 대상");
if(risky.length){fail++;console.log("  ❌ null에 리스너: "+risky.join(", "));}
else console.log("  ✅ 안전");

console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 DOM 참조 이상 없음");
process.exit(fail?1:0);
