const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/automatic-review.js','utf8');const end=code.indexOf('function lockCheckInputs()');
function el(tag,text,cls){return {tag,textContent:text,className:cls,children:[],append(...children){this.children.push(...children)},replaceChildren(){this.children=[]}}}
const root=el('div'),ctx={el,$:()=>root,task:{id:'task',locations:[{id:'C001',members:[{match:{status:'matched'}}]},{id:'C002',members:[{match:{status:'matched'}}]}],evidence_review:{locations:[{location_id:'C001',state:'complete',material_complete:true,combined:{status:'支持'},claims:[]}]}}};
vm.createContext(ctx);vm.runInContext(code.slice(0,end),ctx);
ctx.renderCheckErrors({task_id:'task',status:'running',completed:1,stage:'检索证据核查 C002 · 第1/2轮',errors:[]});
assert.equal(root.hidden,false);assert.equal(root.children.filter(c=>c.className?.includes('check-summary-line')).length,2);assert(!root.children.some(c=>c.className==='check-issue'));
assert.equal(ctx.userCheckStage({stage:'检索证据核查 C002 · 第1/2轮'}),'正在检查 C002');assert.equal(ctx.userCheckStage({stage:'检索证据核查 C002 · 第2/2轮'}),'正在补充 C002 的证据');
ctx.renderCheckErrors({task_id:'task',status:'partial',completed:2,errors:['C002：模型返回非完整 JSON']});assert.equal(root.children.length,2);assert.equal(root.children[1].children[0].textContent,'C002');
console.log('Running and terminal views use compact rows; retrieval rounds stay out of primary status.');
ctx.clearTimeout=()=>{};ctx.pollTimer=null;ctx.requestEpoch=0;
ctx.task.locations[0].members[0].match.status='unmatched';
ctx.resetCheckFeedback();
assert(root.children.every(c=>!c.className?.includes('check-summary-success')));
const waiting=root.children.map(line=>line.children?.[1]?.children?.[0]?.textContent||'');
assert(waiting.every(t=>t==='：等待检查'));assert.equal(ctx.requestEpoch,1);
console.log('Restart immediately replaces old errors and verdicts with waiting rows.');
