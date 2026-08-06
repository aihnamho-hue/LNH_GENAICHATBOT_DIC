// 100% 초과 구간에서 "흔들림은 한 번, 버닝은 유지"인지 확인
const fs=require("fs");
const src=fs.readFileSync(process.argv[2]||require("path").join(__dirname,"templates","index.html"),"utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};

ok("body를 흔들지 않는다", !/document\.body\.classList\.(add|remove)\("zap-shake"\)/.test(src));
ok("패널(.app/.home-screen)을 흔든다", /\.app\.zap-shake, \.home-screen\.zap-shake/.test(src));
ok("zapDone 잠금 있음", /if \(zapDone\) return;\s*\n\s*zapDone = true;/.test(src));
ok("세션 시작 시 초기화", /zapDone = false;/.test(src));
ok("버닝(.over) 애니메이션 유지", /\.progress-bar\.over[^}]*animation: burn/.test(src));
ok("prefers-reduced-motion 대응", /prefers-reduced-motion[\s\S]{0,120}zap-shake \{ animation: none/.test(src));

// screenZap 을 실제로 여러 번 불러 본다
const m=src.match(/let zapTimer = null;[\s\S]*?\n    \}/);
let shakes=0, sounds=0;
const el={classList:{remove(){},add(){shakes++;}},offsetWidth:0};
const ctx={ zapTimer:null, zapDone:false, playZap(){sounds++;},
  document:{querySelector:(q)=>q.includes('data-screen="home"')?null:el},
  clearTimeout(){}, setTimeout(){} };
const fn=new Function("ctx", `with(ctx){ ${m[0]} ; return screenZap; }`)(ctx);
for(let i=0;i<6;i++) fn();
ok(`여섯 턴 호출 → 흔들림 ${shakes}회 (1이어야)`, shakes===1);
ok(`여섯 턴 호출 → 소리 ${sounds}회 (1이어야)`, sounds===1);
console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
process.exit(fail?1:0);
