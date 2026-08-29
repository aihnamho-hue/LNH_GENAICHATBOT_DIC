const fs=require('fs');const {JSDOM,VirtualConsole}=require('jsdom');
const SRC="app.html";
const vc=new VirtualConsole();let err=0;vc.on('jsdomError',e=>{err++;console.log('  ✗',String(e).slice(0,180));});
const dom=new JSDOM(fs.readFileSync(SRC,'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,url:'http://localhost/',virtualConsole:vc,
 beforeParse(w){w.fetch=()=>Promise.resolve({ok:false,status:0,json:()=>Promise.resolve({})});
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.play=()=>Promise.resolve();w.HTMLMediaElement.prototype.pause=()=>{};w.HTMLMediaElement.prototype.load=()=>{};
  w.AudioContext=w.webkitAudioContext=function(){const g={gain:{value:0,cancelScheduledValues(){},setValueAtTime(){},linearRampToValueAtTime(){}},connect:x=>x,disconnect(){}};
    return {state:'running',currentTime:0,destination:{},createGain:()=>g,createMediaElementSource:()=>g,createMediaStreamSource:()=>g,createAnalyser:()=>Object.assign({},g,{fftSize:512,getFloatTimeDomainData(){}}),resume:()=>Promise.resolve(),close:()=>Promise.resolve()};};
 }});
const w=dom.window;
let bad=0; const ok=(m,c,x)=>{console.log((c?"  ✅ ":"  ❌ ")+m+(c?"":"   "+(x===undefined?"":x)));if(!c)bad++;};
setTimeout(()=>{
  if(err){console.log("💥 화면이 죽었다");process.exit(1);}
  const grab = () => { const fd=new w.FormData(); w.eval('window.__fd = arguments')  ; return fd; };
  // 대화록은 발화가 하나라도 있어야 만들어진다
  w.eval('transcriptLog.push({role:"user", text:"안녕하세요"}); sessionStartedAt = new Date();');
  ["free","rp"].forEach(m=>{
    w.eval(`setMode(${JSON.stringify(m)})`);
    const got = w.eval('sessionMode()');
    ok(`setMode("${m}") → sessionMode()="${m}"`, got===m, got);
    const meta = w.eval('buildSessionMeta()');
    ok(`  meta.mode 도 "${m}"`, meta.mode===m, meta.mode);
    const txt = w.eval('buildTranscriptText()');
    const want = m==="rp" ? "주제 대화" : "자유 대화";
    ok(`  대화록에 「연습 갈래: ${want}」`, txt.indexOf("연습 갈래: "+want)>=0,
       (txt.split("\n").find(l=>l.indexOf("연습 갈래")>=0)||"없음"));
  });
  // FormData 에 실제로 실리는가
  w.eval('setMode("rp")');
  const fd = new w.FormData();
  w.eval('window.__t = function(fd){ appendCommonFields(fd); return fd.get("mode"); }');
  ok("FormData 에 mode 가 실린다", w.__t(fd)==="rp", w.__t(fd));
  const src=fs.readFileSync(SRC,'utf8');
  ok("보내는 자리가 한 군데다 (appendCommonFields)", (src.match(/fd\.append\("mode"/g)||[]).length===1);
  console.log(bad?`\n💥 ${bad}건`:"\n🎉 주제·자유가 갈려서 저장된다");
  process.exit(bad?1:0);
},1200);
