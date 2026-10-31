/* SFC pixel reference analyzer v6: browser-only, original source pixels are never exported. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),root=$('pixelStudio'),sel=$('studioSource');
if(!root||!sel||$('analysisLab'))return;
const style=document.createElement('style');
style.textContent='#analysisLab .labline{font-size:12px;color:#cadbe6}#analysisLab .labwarn{padding:9px;margin:8px 0;border:1px solid #796444;background:#30281b;border-radius:8px;font-size:12px}#analysisLab .labmap{max-height:350px;overflow:auto;background:#172533;border:1px solid #516879;border-radius:8px;padding:7px}#analysisLab #labCanvas{display:block;image-rendering:pixelated;max-width:none;touch-action:manipulation}#analysisLab .labgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:10px 0}#analysisLab .labcard{padding:8px;border:1px solid #475c70;border-radius:7px;min-width:0;background:#132130}#analysisLab .labvalue{font-size:17px;font-weight:700}#analysisLab .labrow{display:grid;grid-template-columns:24px 1fr 64px;gap:4px;align-items:center;font-size:11px;padding:2px 0}#analysisLab .labbar{height:12px;background:#243445;overflow:hidden}#analysisLab .labspan{height:100%;background:#88c4ca}#analysisLab .labrows{overflow:auto;max-height:260px;padding:8px;background:#11202b;border-radius:8px}#analysisLab .labcolors{display:flex;flex-wrap:wrap;gap:5px}#analysisLab .labcolor{font-size:11px;padding:4px;border:1px solid #536678;border-radius:6px}#analysisLab .labchip{display:inline-block;width:18px;height:18px;vertical-align:middle;border-radius:3px;border:1px solid #73838f;margin-right:5px}#analysisLab .labmarks{display:flex;flex-wrap:wrap;gap:5px}#analysisLab .labmarks button{min-height:34px;font-size:11px;padding:5px}#analysisLab .labactions{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0}#analysisLab h3{font-size:14px;margin:12px 0 6px}#analysisLab select{width:auto;min-height:42px}#analysisLab .labsub{font-size:12px;line-height:1.6;color:#bbcad8}@media(min-width:760px){#analysisLab .labcolumns{display:grid;grid-template-columns:1fr 1fr;gap:18px}}';
document.head.append(style);
const section=document.createElement('section');section.id='analysisLab';
section.innerHTML=[
'<h2>原作ドット解析ラボ <span class="tag">v6 原寸解析</span></h2>',
'<p class="labsub">原作マムルなどを1px単位で測定。原作PNGの画素が取得できた場合のみ数値を表示します。目・口・ハイライトは手動で位置を記録します。</p>',
'<div id="labNotice" class="labwarn">原作画像を読み込み中です。</div>',
'<div class="labactions"><button type="button" id="labPickFile">原寸PNGを選ぶ（iPhone）</button><a id="labDirectImage" class="source" target="_blank" rel="noopener">原寸PNGを開く</a><a id="labSourcePage" class="source" target="_blank" rel="noopener">出典ページ</a></div>',
'<div class="labactions"><button type="button" id="labAgain">再解析</button><button type="button" id="labExport">解析レポートJSONを保存</button></div>',
'<div class="labcolumns"><div><h3>原作1pxマップ（タップで座標記録）</h3><div class="labmap"><canvas id="labCanvas" width="16" height="18" aria-label="原作ピクセルマップ"></canvas></div>',
'<div class="labline" id="labPicked">マップをタップすると位置・色・透明度が表示されます。</div>',
'<div class="labactions"><select id="labRole"><option>左目</option><option>右目</option><option>口</option><option>ハイライト</option><option>影</option><option>輪郭</option><option>その他</option></select><button id="labClearMarks">注目点を消去</button></div>',
'<div class="labmarks" id="labMarks"></div><p class="labsub">役割は自動判定しません。タップした位置だけ保存します。</p>',
'<h3>使用色上位12色</h3><div id="labColors" class="labcolors"></div></div>',
'<div><h3>輪郭と色の実測</h3><div class="labgrid">',
'<div class="labcard"><div class="labsub">原作：寸法・色数</div><div id="labRefInfo" class="labvalue">未解析</div></div>',
'<div class="labcard"><div class="labsub">オリジナル：寸法・色数</div><div id="labWorkInfo" class="labvalue">未解析</div></div>',
'<div class="labcard"><div class="labsub">原作：描画数 / 有効範囲</div><div id="labRefShape" class="labvalue">未解析</div></div>',
'<div class="labcard"><div class="labsub">オリジナル：描画数 / 有効範囲</div><div id="labWorkShape" class="labvalue">未解析</div></div></div>',
'<p class="labsub" id="labCheck"></p>',
'<h3>各行の形（左端–右端 / 実際の画素数）</h3><div id="labRows" class="labrows">未解析</div>',
'<h3>量産用の分析メモ</h3><p id="labBrief" class="labsub">画像取得後、測定結果から作成します。</p></div></div>',
'<p class="labsub">※参照画像そのものはダウンロード用データに含めません。半透明画素や孤立点は技術チェックであり、美しさを数値だけで採点するものではありません。原作の出典・著作権は元サイトを参照してください。</p>'
].join('');
root.before(section);
const c=$('labCanvas'),cx=c.getContext('2d',{willReadFrequently:true});
let ref=null,name='',marks=[],generation=0,lastReport=null;
const status=s=>$('labNotice').textContent=s;
const color=(r,g,b)=>'#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('').toUpperCase();
function metrics(data,w,h){
 let n=0,semi=0,alone=0,dark=0,bright=0,minX=w,minY=h,maxX=-1,maxY=-1;
 const counts=new Map(),rows=[];
 for(let y=0;y<h;y++){
  let start=w,end=-1,num=0;
  for(let x=0;x<w;x++){
   let k=4*(y*w+x),a=data[k+3];
   if(a>0&&a<255)semi++;
   if(a<128)continue;
   n++;num++;start=Math.min(x,start);end=Math.max(x,end);
   minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);
   const hex=color(data[k],data[k+1],data[k+2]);
   counts.set(hex,(counts.get(hex)||0)+1);
   const l=.2126*data[k]+.7152*data[k+1]+.0722*data[k+2];
   if(l<80)dark++;if(l>180)bright++;
   let near=0;
   for(const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]){
    const ax=x+dx,ay=y+dy;if(ax>=0&&ay>=0&&ax<w&&ay<h&&data[4*(ay*w+ax)+3]>=128)near++;
   }
   if(!near)alone++;
  }
  rows.push({y,left:num?start:null,right:num?end:null,span:num?end-start+1:0,pixels:num});
 }
 return {width:w,height:h,colors:[...counts].sort((a,b)=>b[1]-a[1]).map(([hex,count])=>({hex,count})),
  colorCount:counts.size,pixels:n,coverage:Math.round(n*1000/(w*h))/10,partialAlpha:semi,isolated:alone,
  bbox:maxX<0?null:{x:minX,y:minY,width:maxX-minX+1,height:maxY-minY+1},
  darkPct:n?Math.round(100*dark/n):0,brightPct:n?Math.round(100*bright/n):0,rows};
}
function renderMap(){
 if(!ref){cx.clearRect(0,0,c.width,c.height);return;}
 const w=ref.w,h=ref.h,s=Math.max(8,Math.min(16,Math.floor(304/w)));c.width=w*s;c.height=h*s;
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const k=4*(y*w+x),alpha=ref.data[k+3];cx.fillStyle=(x+y)%2?'#223342':'#2a4050';cx.fillRect(x*s,y*s,s,s);
  if(alpha){cx.fillStyle='rgba('+ref.data[k]+','+ref.data[k+1]+','+ref.data[k+2]+','+(alpha/255)+')';cx.fillRect(x*s,y*s,s,s);}
 }
 cx.strokeStyle='rgba(255,255,255,.20)';cx.lineWidth=1;cx.beginPath();
 for(let x=0;x<=w;x++){cx.moveTo(x*s+.5,0);cx.lineTo(x*s+.5,h*s);}
 for(let y=0;y<=h;y++){cx.moveTo(0,y*s+.5);cx.lineTo(w*s,y*s+.5);}cx.stroke();
 for(const mark of marks)if(mark.x<w&&mark.y<h){cx.strokeStyle='#FFE45C';cx.lineWidth=2;cx.strokeRect(mark.x*s+1,mark.y*s+1,s-2,s-2);}
}
const markKey=()=> 'shiren_ref_marks_v3_'+name;
function saveMarks(){try{localStorage.setItem(markKey(),JSON.stringify(marks))}catch{}}
function loadMarks(){try{const a=JSON.parse(localStorage.getItem(markKey())||'[]');marks=Array.isArray(a)?a.filter(x=>Number.isInteger(x.x)&&Number.isInteger(x.y)&&typeof x.role==='string').slice(0,50):[];}catch{marks=[]}}
function renderMarks(){
 const box=$('labMarks');box.replaceChildren();
 for(let i=0;i<marks.length;i++){
  const m=marks[i],b=document.createElement('button');b.textContent=m.role+' ('+m.x+','+m.y+') ×';
  b.onclick=()=>{marks.splice(i,1);saveMarks();renderMarks();renderMap();renderInfo();};box.append(b);
 }
}
function renderRows(m){
 const box=$('labRows');box.replaceChildren();if(!m){box.textContent='画素を取得できていません';return;}
 for(const r of m.rows){
  const row=document.createElement('div');row.className='labrow';
  const a=document.createElement('span');a.textContent=r.y;
  const bar=document.createElement('div');bar.className='labbar';
  if(r.left!==null){
   const seg=document.createElement('div');seg.className='labspan';seg.style.marginLeft=(100*r.left/m.width)+'%';seg.style.width=(100*r.span/m.width)+'%';bar.append(seg);
  }
  const b=document.createElement('span');b.textContent=r.left===null?'空':(r.left+'–'+r.right+' / '+r.pixels);
  row.append(a,bar,b);box.append(row);
 }
}
function renderColors(m){
 const box=$('labColors');box.replaceChildren();
 if(!m){box.textContent='未解析';return;}
 for(const item of m.colors.slice(0,12)){
  const d=document.createElement('span'),chip=document.createElement('span');
  d.className='labcolor';chip.className='labchip';chip.style.background=item.hex;
  d.append(chip,document.createTextNode(item.hex+' '+item.count+'px'));box.append(d);
 }
}
function workMetrics(){
 try{const work=$('studioCanvas');if(!work||!work.width)return null;return metrics(work.getContext('2d',{willReadFrequently:true}).getImageData(0,0,work.width,work.height).data,work.width,work.height);}catch{return null;}
}
const textInfo=m=>m?(m.width+'×'+m.height+' / '+m.colorCount+'色'):'未解析';
const textShape=m?(m.pixels+'px / '+(m.bbox?(m.bbox.width+'×'+m.bbox.height):'空白')):'未解析';
function renderInfo(){
 const r=ref&&ref.metrics,w=workMetrics();
 $('labRefInfo').textContent=textInfo(r);$('labRefShape').textContent=textShape(r);
 $('labWorkInfo').textContent=textInfo(w);$('labWorkShape').textContent=textShape(w);
 $('labCheck').textContent='原作：'+(r?(r.partialAlpha+'半透明 / '+r.isolated+'孤立点'):'未測定')+' ／ 制作中：'+(w?(w.partialAlpha+'半透明 / '+w.isolated+'孤立点'):'未測定');
 $('labBrief').textContent=r?(name+'：'+r.width+'×'+r.height+'px / '+r.colorCount+'色、描画'+r.pixels+'px ('+r.coverage+'%)。濃色約'+r.darkPct+'%、明色約'+r.brightPct+'%（明度で分類）。輪郭の各行・目の位置はマップで確認。これらを参考に、別の造形のオリジナルを制作する。'):
  '原寸PNGを読み込むと数値を実測できます。読み込み前は色数や陰影の情報を推測しません。';
 lastReport={format:'sfc-pixel-analysis',version:3,source:name,sourcePage:DATA.find(x=>x.name===name)?.source_page||'',measured:!!r,reference:r||null,original:w||null,manualMarks:marks,
 note:'実測した集計値と人手の注目点のみ。原作PNGの全画素や元画像は含みません。'};
}
function ingest(img,origin){
 try{
  if(img.width>128||img.height>128||img.width<1||img.height<1)throw Error('原寸128px以内の画像を指定してください');
  const tmp=document.createElement('canvas');tmp.width=img.width;tmp.height=img.height;
  const ctx=tmp.getContext('2d',{willReadFrequently:true});ctx.imageSmoothingEnabled=false;ctx.drawImage(img,0,0);
  const bytes=ctx.getImageData(0,0,tmp.width,tmp.height).data;
  ref={data:new Uint8ClampedArray(bytes),w:tmp.width,h:tmp.height,metrics:metrics(bytes,tmp.width,tmp.height)};
  renderMap();renderColors(ref.metrics);renderRows(ref.metrics);renderInfo();
  status(origin+' '+ref.w+'×'+ref.h+'px / '+ref.metrics.colorCount+'色 / '+ref.metrics.pixels+'画素を実測しました。');
 }catch(e){ref=null;renderInfo();status('画像の画素を取得できません。原寸PNGを端末に保存し、上の「原作PNGをファイルから読み込んで解析」で読み込んでください。');}
}
async function remote(){
 name=sel.value;ref=null;loadMarks();renderMarks();renderMap();renderColors(null);renderRows(null);renderInfo();
 const entry=DATA.find(x=>x.name===name);if(!entry)return;
 $('labDirectImage').href=entry.image_url;$('labSourcePage').href=entry.source_page;
 status(name+' の画像を解析中です（直接取得 → 代替経路）…');
 const id=++generation;
 try {
  const loaded=await window.SfcReferenceLoader.load(entry.image_url,entry.width,entry.height);
  if(id===generation)ingest(loaded.img,loaded.via==='proxy'?'代替経路のPNGから解析：':'原作サイトから解析：');
 } catch(err) {
  if(id===generation)status('原作画像は表示できても、自動の画素解析は外部サイトの制限で失敗します。①「原寸PNGを開く」で保存 → ②「原寸PNGを選ぶ」でファイルを指定してください。');
 }
}
$('labAgain').onclick=remote;
$('labPickFile').onclick=()=>{$('studioReferenceFile')?.click();};
$('labClearMarks').onclick=()=>{if(marks.length&&confirm('記録した注目点を消しますか？')){marks=[];saveMarks();renderMarks();renderMap();renderInfo();}};
c.addEventListener('click',event=>{
 if(!ref)return;const box=c.getBoundingClientRect();
 const x=Math.floor((event.clientX-box.left)*ref.w/box.width),y=Math.floor((event.clientY-box.top)*ref.h/box.height);
 if(x<0||x>=ref.w||y<0||y>=ref.h)return;
 const k=4*(y*ref.w+x),a=ref.data[k+3],hex=color(ref.data[k],ref.data[k+1],ref.data[k+2]);
 $('labPicked').textContent='('+x+', '+y+') '+(a<128?'透明':hex)+' / alpha '+a;
 const role=$('labRole').value;marks=marks.filter(v=>v.role!==role);marks.push({role,x,y,color:a<128?null:hex});
 saveMarks();renderMarks();renderMap();renderInfo();
});
$('labExport').onclick=()=>{
 renderInfo();const blob=new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=url;a.download='sfc_'+name.replace(/[^a-z\d_-]/gi,'_')+'_analysis.json';
 document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),12000);
};
sel.addEventListener('change',remote);
window.addEventListener('shiren:reference-loaded',event=>{
 const detail=event.detail||{},img=detail.image;
 if(!img)return;
 ++generation;name=sel.value;loadMarks();renderMarks();
 if(detail.width>128||detail.height>128){
  ref=null;renderMap();renderColors(null);renderRows(null);renderInfo();
  status('画像は読み込めましたが '+detail.width+'×'+detail.height+'px です。原作のドットを正確に測るには128px以下の原寸PNGが必要です。');
  return;
 }
 ingest(img,'端末からの原寸画像：');
});
const cap=$('studioWorkCaption');
if(cap)new MutationObserver(()=>requestAnimationFrame(renderInfo)).observe(cap,{characterData:true,childList:true,subtree:true});
remote();
})();