const fs=require('fs'),vm=require('vm'),assert=require('assert');
const app=fs.readFileSync('web/app.js','utf8'),automatic=fs.readFileSync('web/automatic-review.js','utf8');
const reset=app.match(/function reset\(\)\{[^}]*\}/)[0];let detached=0;
const context={task:{},$:()=>({hidden:false}),window:{detachCheck(){detached++}}};vm.createContext(context);vm.runInContext(reset+';reset()',context);assert.equal(detached,1,'draft changes must detach the prior check');

let store={'backed-up-active-check':'old'},cleared=0;const progress={hidden:false};
const state={activeCheck:'old',pollTimer:3,requestEpoch:0,window:{},localData:{removeItem(k){delete store[k]}},clearTimeout(){cleared++},$:()=>progress};vm.createContext(state);
vm.runInContext(automatic.match(/window\.detachCheck=function\(\)\{[^}]*\}/)[0]+';window.detachCheck()',state);assert.equal(state.activeCheck,null);assert.equal(state.requestEpoch,1);assert.equal(store['backed-up-active-check'],undefined);assert.equal(cleared,1);assert.equal(progress.hidden,true);

// Exercise the real new-check handler and overview wrapper together: the wrapper
// must not resurrect the previous terminal job's progress card.
const overview=fs.readFileSync('web/overview.js','utf8'),nodes={};
const fresh={activeCheck:'old',pollTimer:3,requestEpoch:0,workspaceView:'input',task:{id:'old'},sources:[{}],window:{isChecking:false,currentCheckJob:{status:'partial',task_id:'old'}},
 localData:{removeItem(){}},clearTimeout(){},$:id=>nodes[id]??={hidden:false,value:'old',textContent:'old'},renderSources(){},saveDraft(){},history:{replaceState(){}},location:{pathname:'/'}};
vm.createContext(fresh);
vm.runInContext(overview.slice(overview.indexOf('function checkPresentation('),overview.indexOf('function syncCheckPresentation(')),fresh);
fresh.showWorkspaceView=()=>{nodes['check-progress'].hidden=!fresh.checkPresentation(fresh.task,fresh.window.currentCheckJob,false).progress};
vm.runInContext(automatic.match(/window\.detachCheck=function\(\)\{[^}]*\}/)[0]+';'+reset,fresh);
vm.runInContext(automatic.split('\n').find(line=>line.startsWith("$('new-check').onclick=")),fresh);
vm.runInContext(overview.split('\n').find(line=>line.startsWith('const previousNewCheck=')),fresh);
nodes['new-check'].onclick();
assert.equal(fresh.window.currentCheckJob,null);assert.equal(fresh.task,null);assert.equal(fresh.activeCheck,null);
assert.equal(nodes['check-progress'].hidden,true);assert.equal(nodes['report'].hidden,true);assert.equal(nodes['text'].value,'');assert.equal(fresh.sources.length,0);
console.log('New check clears the terminal card even after overview navigation.');

vm.runInContext(automatic.slice(automatic.indexOf('async function pollCheck()'),automatic.indexOf("$('run').onclick=")),fresh);
(async()=>{
 let reject;fresh.activeCheck='old';fresh.api=()=>new Promise((_,fail)=>{reject=fail});
 const pending=fresh.pollCheck();nodes['new-check'].onclick();reject(Error('old polling error'));await pending;
 assert.equal(nodes['error'].hidden,true,'an old in-flight error must not affect the new draft');
 let resolve,shown=0;fresh.activeCheck='old';fresh.showJob=()=>shown++;fresh.api=()=>new Promise(done=>{resolve=done});
 const response=fresh.pollCheck();nodes['new-check'].onclick();resolve({status:'partial',task_id:'old'});await response;
 assert.equal(shown,0,'an old in-flight result must not restore the previous card');
 console.log('Late polling results and errors cannot restore the old check.');
})().catch(error=>{console.error(error);process.exit(1)});
