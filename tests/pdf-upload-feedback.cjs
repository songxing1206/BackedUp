const fs=require('fs'),vm=require('vm'),assert=require('assert');
function fixture(api){
 const nodes={},ctx={window:{},sources:[],token:'',api,$:id=>nodes[id]??={hidden:false,textContent:'old',disabled:false,items:[],replaceChildren(){this.items=[]},append(item){this.items.push(item)}},el:(tag,text)=>({text}),pdfHash:async s=>s.hash,digest:async bytes=>bytes,merge:async rows=>ctx.sources.push(...rows),FileReader:class{readAsDataURL(){this.result='data:application/pdf;base64,Zml4dHVyZQ==';this.onload()}}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/uploads.js','utf8'),ctx);return {ctx,nodes};
}
const file=(name,size=10)=>({name,size,arrayBuffer:async()=>name});
(async()=>{
 let calls=0;let f=fixture(async()=>{calls++;throw TypeError('Failed to fetch')});
 const folder=f.ctx.folderPdfFiles([{name:'papers/a.pdf'},{name:'notes.txt'},{name:'B.PDF'}]);assert.deepEqual(folder.pdfs.map(x=>x.name),['papers/a.pdf','B.PDF']);assert.equal(folder.ignored,1);
 await f.ctx.uploadPdfs(Array.from({length:43},(_,i)=>file(i+'.pdf')));
 assert.equal(calls,1);assert.match(f.nodes['upload-status'].textContent,/尚未上传 43 篇/);assert.match(f.nodes['upload-status'].textContent,/失败 0 篇/);
 assert.equal(f.nodes['error'].hidden,true);assert.equal(f.nodes['upload-errors'].items.length,1);assert.equal(f.nodes['pdf-files'].disabled,false);
 let uploads=0;f=fixture(async path=>{if(path==='/api/config')return {token:'fixture'};assert.equal(path,'/api/assets');if(++uploads===2)throw TypeError('Failed to fetch');return {id:'fixture'}});
 await f.ctx.uploadPdfs([file('one.pdf'),file('two.pdf'),file('three.pdf')]);
 assert.equal(uploads,2);assert.match(f.nodes['upload-status'].textContent,/新增 1 篇.*失败 1 篇.*尚未上传 1 篇/);assert.equal(f.nodes['upload-errors'].items.length,1);
 f=fixture(async path=>path==='/api/config'?{token:'fixture'}:{id:'fixture'});
 await f.ctx.uploadPdfs([file('large.pdf',16*1024*1024),file('good.pdf')]);
 assert.match(f.nodes['upload-status'].textContent,/新增 1 篇.*失败 1 篇/);assert.match(f.nodes['upload-errors'].items[0].text,/15 MB/);
 await f.ctx.uploadPdfs([file('again.pdf')]);assert.equal(f.nodes['upload-errors'].hidden,true);assert.equal(f.nodes['upload-errors'].items.length,0);
 console.log('PDF upload: local feedback, offline preflight, interrupted batch, per-file error and clean retry passed.');
})().catch(error=>{console.error(error);process.exit(1)});
