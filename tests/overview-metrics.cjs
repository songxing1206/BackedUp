const fs=require('fs'),vm=require('vm'),assert=require('assert');const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/overview.js','utf8').split("let workspaceView")[0],ctx);
const location=(id,status='matched')=>({id,members:[{author:'Smith',year:'2023',match:{status}}]});
const review=(id,status,state='complete')=>({location_id:id,state,combined:{status}});
const data={locations:[location('C1'),location('C2'),location('C3'),location('C4','unmatched'),location('C5','unmatched')],evidence_review:{locations:[review('C1','支持'),review('C2','部分支持'),review('C3','支持','pending')]}};
const m=ctx.overviewMetrics(data);assert.equal(m.correct,1);assert.equal(m.reviewed,2);assert.equal(m.total,5);assert.equal(m.manual,3);assert.equal(m.missing,1);assert.equal(m.accuracy,50);assert.equal(m.completion,40);
assert.equal(ctx.overviewMetrics({locations:[]}).accuracy,null);
assert.deepEqual(JSON.parse(JSON.stringify(ctx.overviewMetrics(null))),{total:0,reviewed:0,correct:0,manual:0,missing:0,completion:null,accuracy:null});
data.evidence_review.locations[0].material_complete=false;assert.equal(ctx.overviewMetrics(data).correct,0);
console.log('Overview metrics passed: final verdict, pending/stale exclusion, rates, zero denominator, missing bibliography dedup.');
