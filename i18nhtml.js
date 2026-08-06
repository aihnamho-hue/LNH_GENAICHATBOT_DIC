// HTML에 박힌 한국어 중, JS가 번역해 덮어쓰지 않는 것 찾기
const fs=require("fs"), {JSDOM}=require("jsdom");
const SRC=process.argv[2]||require("path").join(__dirname,"templates","index.html");
const html=fs.readFileSync(SRC,"utf8");
const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const dom=new JSDOM(html.replace(/<script>[\s\S]*?<\/script>/g,""));
const d=dom.window.document;

// JS가 textContent/innerHTML/placeholder 를 건드리는 id 목록
const touched=new Set();
for(const re of [/getElementById\("([A-Za-z0-9_]+)"\)\s*\.\s*(?:textContent|innerText|innerHTML|placeholder|value|title)/g,
                 /getElementById\("([A-Za-z0-9_]+)"\)\.textContent/g]){
  let m; while((m=re.exec(script))) touched.add(m[1]);
}
// 변수에 담아 쓰는 경우도 잡는다:  const x = document.getElementById("id"); … x.textContent =
let m2, reV=/(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*document\.getElementById\("([A-Za-z0-9_]+)"\)/g;
const varOf={}; while((m2=reV.exec(script))) varOf[m2[1]]=m2[2];
for(const v in varOf){
  if(new RegExp(`\\b${v}\\.(textContent|innerText|innerHTML|placeholder|value|title)\\s*=`).test(script)) touched.add(varOf[v]);
}
// querySelector('#id') 형태
let m3, reQ=/querySelector(?:All)?\(["'`]#([A-Za-z0-9_]+)/g;
while((m3=reQ.exec(script))) touched.add(m3[1]);

const hangul=/[가-힣]/;
// 일부러 한국어로 두는 것 — 출처 표기 · 앱 이름 · 언어 이름 · 언어 선택 전 이중 표기
const OK_KOREAN=[/credit/,/lang-item/,/inapp-body/,/home-title/,/^H2$/];
// data-* 로 번역되는 요소(예: data-qkey)는 JS가 갱신한다
const SKIP=new Set(["SCRIPT","STYLE","NOSCRIPT"]);
const found=[];
const walk=(n)=>{
  if(n.nodeType===3){
    const txt=n.textContent.trim();
    if(txt.length>1 && hangul.test(txt)){
      // 조상 중 JS가 건드리는 id가 있으면 통과
      let p=n.parentElement, covered=false, path=[];
      while(p && p.tagName!=="BODY"){
        if(p.id){ path.push("#"+p.id); if(touched.has(p.id)) {covered=true;break;} }
        p=p.parentElement;
      }
      // data-i18n 계열 속성이 있으면 JS가 갱신한다
      let q=n.parentElement; while(q && q.tagName!=="BODY"){ if([...q.attributes].some(a=>/^data-(qkey|i18n)/.test(a.name))){covered=true;break;} q=q.parentElement; }
      const cls=(n.parentElement.className||"")+" "+n.parentElement.tagName;
      if(!covered && OK_KOREAN.some(r=>r.test(cls))) covered=true;
      if(!covered) found.push({txt:txt.slice(0,42), where:(n.parentElement.id?"#"+n.parentElement.id:n.parentElement.className||n.parentElement.tagName)});
    }
    return;
  }
  if(n.nodeType!==1 || SKIP.has(n.tagName)) return;
  // placeholder / title / alt 도 본다
  for(const a of ["placeholder","title","aria-label"]){
    const v=n.getAttribute&&n.getAttribute(a);
    if(v && hangul.test(v) && !(n.id&&touched.has(n.id))) found.push({txt:`[${a}] ${v.slice(0,36)}`, where:n.id?"#"+n.id:n.className||n.tagName});
  }
  for(const c of n.childNodes) walk(c);
};
walk(d.body);
console.log(`── HTML에 박혀 있고 JS가 안 바꾸는 한국어 ──`);
if(!found.length) console.log("  ✅ 없음");
else { console.log(`  ⚠️ ${found.length}건`); found.slice(0,30).forEach(f=>console.log(`   · ${f.where}  →  ${f.txt}`)); }
