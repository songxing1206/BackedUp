const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/automatic-review.js','utf8').split('function renderCompactCheckSummary')[0];
const context={};vm.createContext(context);vm.runInContext(code,context);
const member=status=>({match:{status}}),review=(id,state='complete',status='支持')=>({location_id:id,state,material_complete:true,combined:{status},claims:[]});
const record={locations:['C001','C002','C003','C004','C005'].map(id=>({id,members:[member(id==='C004'?'needs_assignment':'matched')]})),evidence_review:{locations:[review('C001'),review('C002','complete','不支持'),review('C003'),review('C005','stale')]}};
let rows=context.checkSummaryRows(record,{errors:['C003：模型返回非完整 JSON']});
assert.deepEqual(Array.from(context.checkSummaryRows(null,null)),[]);
assert.equal(rows.length,5);assert.equal(rows[0].text,'已成功检查');assert.equal(rows[1].text,'已成功检查');assert.equal(rows[2].ok,false);assert.match(rows[2].text,/模型未返回完整结果/);assert.match(rows[3].text,/文献信息缺失/);assert.match(rows[4].text,/尚未完成/);
record.evidence_review.locations[0].material_complete=false;rows=context.checkSummaryRows(record,{errors:[]});assert.equal(rows[0].ok,false);
console.log('Compact summary: all positions, completion vs support, error priority, missing source and stale result passed.');

rows=context.checkSummaryRows(record,{status:'running',completed:2,stage:'检索证据核查 C003 · 第1/2轮',errors:[]});
assert.equal(rows[2].text,'正在检查');assert.match(rows[4].text,/等待检查/);
record.evidence_review.locations=record.evidence_review.locations.filter(r=>r.location_id!=='C003');
rows=context.checkSummaryRows(record,{status:'running',completed:2,stage:'检索证据核查 C003 · 第1/2轮',errors:[]});assert.equal(rows[2].text,'正在检查');
assert.equal(context.checkSummaryRows(record,{errors:[],location_limit:3}).length,3);
assert.equal(context.checkSummaryRows(record,{errors:[],location_ids:['C002']}).length,1);
