const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/automatic-review.js','utf8').split('function showJob(job){')[1].split('async function pollCheck')[0];
const nodes={},context={window:{},$:id=>nodes[id]??={},lockCheckInputs(){},userCheckStage:j=>j.stage,renderCheckErrors(j){(nodes['check-errors']??={}).hidden=!j.errors?.length}};
vm.createContext(context);vm.runInContext('function showJob(job){'+code,context);
context.showJob({status:'failed',stage:'检查中断',completed:0,total:27,errors:['本地超限原因']});
assert.equal(nodes['check-errors'].hidden,false);
context.showJob({status:'completed',stage:'结束',completed:27,total:27,errors:[]});
assert.equal(nodes['check-errors'].hidden,true);
console.log('Terminal errors remain visible; clean completion clears errors.');
