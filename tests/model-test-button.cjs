const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync('web/model-settings.js','utf8');
const handler=code.slice(code.indexOf("$('model-test').onclick=async"),code.indexOf(";$('model-clear').onclick"));
async function scenario(fail){
 const nodes=Object.fromEntries(['model-test','model-save','model-clear','model-feedback'].map(id=>[id,{disabled:false,textContent:''}]));
 let finish;const gate=new Promise(resolve=>finish=resolve);
 const ctx={$:id=>nodes[id],token:'test',modelConfig:{provider:'codex',model:'',base_url:''},AbortController,setTimeout,clearTimeout,saveModel:async()=>{},fetch:async()=>{await gate;if(fail)throw Error('网络失败');return {ok:true,json:async()=>({message:'成功',provider:'codex',model:'默认'})}}};
 vm.createContext(ctx);vm.runInContext(handler,ctx);const pending=nodes['model-test'].onclick();
 assert(nodes['model-test'].disabled);assert(nodes['model-save'].disabled);
 finish();await pending;assert.equal(nodes['model-test'].disabled,false);assert.equal(nodes['model-save'].disabled,false);assert.equal(nodes['model-test'].textContent,'测试连接');
 assert(nodes['model-feedback'].textContent.includes(fail?'网络失败':'成功'));
}
(async()=>{await scenario(false);await scenario(true);console.log('Model test button: busy state, success and failure recovery passed.')})();
