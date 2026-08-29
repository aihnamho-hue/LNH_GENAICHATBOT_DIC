const fs=require('fs');const {JSDOM,VirtualConsole}=require('jsdom');
const SRC="app.html";
const vc=new VirtualConsole();let err=0;vc.on('jsdomError',e=>{err++;console.log('  ✗ JS 사망:',String(e).slice(0,190));});
const dom=new JSDOM(fs.readFileSync(SRC,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/',virtualConsole:vc,
 beforeParse(w){w.fetch=()=>Promise.resolve({ok:false,status:0,json:()=>Promise.resolve({})});
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.play=()=>Promise.resolve();w.HTMLMediaElement.prototype.pause=()=>{};w.HTMLMediaElement.prototype.load=()=>{};
  w.AudioContext=w.webkitAudioContext=function(){const g={gain:{value:0,cancelScheduledValues(){},setValueAtTime(){},linearRampToValueAtTime(){}},connect:x=>x,disconnect(){}};
    return {state:'running',currentTime:0,destination:{},createGain:()=>g,createMediaElementSource:()=>g,createMediaStreamSource:()=>g,createAnalyser:()=>Object.assign({},g,{fftSize:512,getFloatTimeDomainData(){}}),resume:()=>Promise.resolve(),close:()=>Promise.resolve()};};
 }});
const w=dom.window, D=w.document;
const tap = el => el.dispatchEvent(new w.MouseEvent("click",{bubbles:true,cancelable:true,view:w}));
let bad=0;
const ok=(m,c,x)=>{console.log((c?"  ✅ ":"  ❌ ")+m+(c?"":"   "+(x===undefined?"":x))); if(!c)bad++;};
setTimeout(()=>{
  if(err){console.log("\n💥 화면이 죽었다");process.exit(1);}
  const ov=D.getElementById("nameOverlay"), inp=D.getElementById("nameInput"),
        okB=D.getElementById("nameOkBtn"), xB=D.getElementById("nameX");
  const shown = () => !ov.classList.contains("hidden");

  console.log("── ① 처음 오는 사람 (이름이 없다)");
  w.localStorage.removeItem("userName");
  w.eval('userName=""; nameShown=false;'); w.eval('showNamePopup()');
  ok("이름 창이 떴다", shown());
  ok("✕ 가 안 보인다", xB.hidden === true, "hidden="+xB.hidden);
  ok("확인 단추가 꺼져 있다", okB.disabled === true);

  console.log("\n── ② 빈 칸으로 확인을 눌러 본다");
  inp.value=""; tap(okB);
  ok("아직 창이 열려 있다 (못 넘어간다)", shown());
  ok("칸이 흔들린다 (.needs)", inp.classList.contains("needs"));
  ok("이름이 안 저장됐다", !w.localStorage.getItem("userName"));

  console.log("\n── ③ 공백만 넣어 본다");
  inp.value="   "; inp.dispatchEvent(new w.Event("input",{bubbles:true})); tap(okB);
  ok("여전히 못 넘어간다", shown());
  ok("확인 단추가 아직 꺼져 있다", okB.disabled === true);

  console.log("\n── ④ ✕ 로 빠져나가려 해 본다");
  xB.hidden=false; tap(xB);           // 화면을 억지로 살려 눌러 본다
  ok("✕ 로도 못 빠져나간다", shown());

  console.log("\n── ⑤ 이름을 쓴다");
  inp.value="바트"; inp.dispatchEvent(new w.Event("input",{bubbles:true}));
  ok("확인 단추가 켜졌다", okB.disabled === false);
  ok("붉은 테두리가 걷혔다", !inp.classList.contains("needs"));
  tap(okB);
  ok("창이 닫혔다", !shown());
  ok("이름이 저장됐다", w.localStorage.getItem("userName")==="바트", w.localStorage.getItem("userName"));

  console.log("\n── ⑥ 이름을 바꾸러 다시 들어온다");
  tap(D.getElementById("homeNameBtn"));
  ok("창이 떴다", shown());
  ok("✕ 가 보인다 (이미 이름이 있으니까)", xB.hidden === false);
  ok("지난 이름이 채워져 있다", inp.value==="바트", inp.value);
  inp.value=""; inp.dispatchEvent(new w.Event("input",{bubbles:true}));
  ok("비우면 확인이 다시 꺼진다", okB.disabled === true);
  tap(xB);
  ok("✕ 로 닫힌다", !shown());
  ok("이름이 그대로 남았다", w.localStorage.getItem("userName")==="바트", w.localStorage.getItem("userName"));

  console.log("\n── ⑦ 이름 없이 안내를 건너뛸 수 있나");
  const src=fs.readFileSync(SRC,'utf8');
  ok("건너뛰기 조건에 이름이 들어 있다", /skipEntryGuide\s*=\s*[^;]*&&\s*!!userName/.test(src));

  console.log(bad?`\n💥 ${bad}건`:"\n🎉 이름 없이는 못 들어간다");
  process.exit(bad?1:0);
},1200);
