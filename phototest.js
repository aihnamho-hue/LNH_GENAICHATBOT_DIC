// 📷 교재 사진으로 상황 채우기 — 화면·동작·안전장치 검사
const fs=require("fs"), {JSDOM}=require("jsdom");
const html=fs.readFileSync("app.html","utf8");
// 지원 언어 수는 늘어난다 — 숫자를 박아 두지 말고 언어 고르기 단추에서 센다
const LANGS=(html.match(/data-lang="[a-z]+"/g)||[]).length;
const py=fs.readFileSync("main.py","utf8");
let fail=0; const ok=(n,c)=>{console.log((c?"  ✅ ":"  ❌ ")+n); if(!c)fail++;};

console.log("── 서버 ──");
ok("사진 엔드포인트 있음", /@app\.post\("\/roleplay-from-photo"\)/.test(py));
ok("이미지 형식 제한", /_PHOTO_MIME\s*=\s*\{/.test(py) && /unsupported_image/.test(py));
ok("용량 제한 8MB", /MAX_PHOTO_BYTES = 8 \* 1024 \* 1024/.test(py) && /image_too_large/.test(py));
ok("★ 사진을 저장하지 않는다", /finally:\s*\n\s*raw = b""/.test(py) && !/photo.*\.write|save\(.*photo/i.test(py));
ok("대화 내용은 지어내지 말라고 지시", /대화의 내용을 지어내지 마라/.test(py));
ok("역할 기본값 = 나 / 친구", /분명하지 않으면 "친구"로 둔다/.test(py) && /분명하지 않으면 "나"로 둔다/.test(py));
ok("장소는 비워 두지 않는다", /\*\*비워 두지 마라\.\*\*/.test(py));
ok("한국어 교재가 아니면 빈 값", /한국어 교재가 아니거나 말하기 활동이 아니면/.test(py));
ok("모국어 병기 요청", /native_line/.test(py));

console.log("\n── 화면 ──");
const dom=new JSDOM(html,{runScripts:"dangerously",url:"https://korean-dic.onrender.com/",pretendToBeVisual:true,
 beforeParse(w){w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
  w.HTMLMediaElement.prototype.play=()=>Promise.resolve(); w.HTMLMediaElement.prototype.pause=()=>{};
  try{w.localStorage.setItem("uiLang","ko");w.localStorage.setItem("userName","남정");w.localStorage.setItem("entryDoneCount","3");w.sessionStorage.setItem("splashSeen","1");}catch(e){}}});
const w=dom.window, d=w.document;
setTimeout(()=>{
  const btn=d.getElementById("rpPhotoBtn"), inp=d.getElementById("rpPhotoInput");
  ok("📷 버튼이 설정 화면에 있다", !!btn);
  ok("카메라로 바로 찍기(capture)", inp && inp.getAttribute("capture")==="environment");
  ok("이미지만 고를 수 있다", inp && inp.getAttribute("accept")==="image/*");
  ok("버튼 문구가 모국어", btn && /교재 사진/.test(d.getElementById("rpPhotoLbl").textContent));
  ok("설정 화면 맨 위에 있다", btn && btn.previousElementSibling && btn.previousElementSibling.id==="rpIntroEl");

  console.log("\n── 안전장치 ──");
  ok("칸을 채울 뿐 대화를 자동 시작하지 않는다", !/roleplay-from-photo[\s\S]{0,900}rpMakeBtn\.click/.test(html));
  ok("다시 찍으면 기존 값을 덮어쓴다", /if \(!el \|\| !v\) return;/.test(html) && !/el\.value\.trim\(\)\) return/.test(html));
  ok("확인하라는 안내가 뜬다", /rpPhotoOk:"교재에서 상황을 가져왔어요\. 맞는지 보고 고쳐 주세요\./.test(html));
  ok("실패 안내가 따로 있다", /rpPhotoErr:/.test(html));
  ok("문구가 지원 언어 전부에", (html.match(/rpPhoto:"/g)||[]).length===LANGS);
  console.log(fail? `\n💥 실패 ${fail}건` : "\n🎉 모두 통과");
  process.exit(fail?1:0);
},900);
