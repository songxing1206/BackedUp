const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/app.js','utf8'),start=code.indexOf('function documentPreviewView'),end=code.indexOf('async function loadDocumentPreview');
function node(tag,text,cls){return {tag,textContent:text,className:cls,children:[],append(...items){this.children.push(...items)}}}
const context={el:node};vm.createContext(context);vm.runInContext(code.slice(start,end),context);
const view=context.documentPreviewView({metadata:{title:'Study',authors:[],year:'2024',doi:'10.1/x'},sections:[{title:'Introduction'}],pages:2,quality:{status:'good'},parser:{version:'test'},first_page_text:'Candidate author line',markdown:'# Study'});
assert.equal(view.className,'document-preview');assert(view.children[0].children.some(item=>item.children.some(x=>x.textContent==='Study')));assert(view.children.some(item=>item.children.some(x=>x.textContent?.includes('未识别到作者'))));
console.log('Document parse preview renders metadata, quality, sections, first-page fallback and Markdown.');
