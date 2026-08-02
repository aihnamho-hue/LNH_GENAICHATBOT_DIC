
const fs=require("fs"), csstree=require("css-tree");
const css=fs.readFileSync("i.html","utf8").match(/<style>([\s\S]*?)<\/style>/)[1];
let errs=0;
csstree.parse(css,{positions:true,onParseError(e){errs++;if(errs<=8)console.log("  ❌",e.message,"(줄",e.line+")");}});
console.log(errs? `💥 CSS 파싱 오류 ${errs}건` : "✅ CSS 문법 오류 없음");
const declared=new Set([...css.matchAll(/(--[a-z0-9-]+)\s*:/g)].map(x=>x[1]));
// 기본값 없이 쓰는 변수만 검사 (var(--x) — var(--x, 1)은 제외)
const used=new Set([...css.matchAll(/var\(\s*(--[a-z0-9-]+)\s*\)/g)].map(x=>x[1]));
const allUsed=new Set([...css.matchAll(/var\(\s*(--[a-z0-9-]+)/g)].map(x=>x[1]));
const missing=[...used].filter(v=>!declared.has(v));
console.log(missing.length? "💥 선언 안 된 변수: "+missing.join(", ") : "✅ 변수 전부 선언됨");
const dead=[...declared].filter(v=>!allUsed.has(v));
console.log("ℹ️ 안 쓰이는 토큰:", dead.length? dead.join(", "):"없음");
process.exit(errs||missing.length?1:0);
