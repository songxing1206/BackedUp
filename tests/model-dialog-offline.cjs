const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map();const calls=[];
function node(id){if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,disabled:false,checked:false,addEventListener(){},showModal(){calls.push('opened')},close(){}});return nodes.get(id)}
const ctx={$:node,token:'',work:()=>{},api:async()=>{calls.push('request');throw Error('offline')}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/model-settings.js','utf8'),ctx);
(async()=>{
 await new Promise(setImmediate);calls.length=0;
 const opening=node('model-open').onclick();assert.equal(calls[0],'opened');assert.equal(node('model-session').checked,true);
 await opening;assert(node('model-feedback').textContent.includes('模型测试尚未发起'));assert(!node('model-test').disabled);
 vm.runInContext('modelConfig={session_only:false}',ctx);vm.runInContext('fillModelForm()',ctx);assert.equal(node('model-session').checked,false);
 node('model-provider').value='custom';node('model-provider').onchange();assert.equal(node('model-url').value,'');
 node('model-provider').value='openai';node('model-provider').onchange();assert.equal(node('model-url').value,'https://api.openai.com/v1');
 const html=fs.readFileSync('web/index.html','utf8');assert(html.includes('API 服务地址（Base URL）'));assert(!html.includes('高级：服务地址'));
 vm.runInContext("modelConfig={provider:'custom',model:'deepseek-reasoner',base_url:'https://models.sjtu.edu.cn/api/v1',reasoning_effort:'high',reasoning_output_tokens:32768,reasoning_timeout_seconds:1800}",ctx);vm.runInContext('fillModelForm()',ctx);
 assert.equal(node('model-id').value,'deepseek-reasoner');assert.equal(node('reasoning-options').hidden,false);assert.equal(node('reasoning-output').value,'32768');
 node('model-id').value='';vm.runInContext('campusModelHint(true)',ctx);assert.equal(node('model-id').value,'');
 console.log('Model dialog opens offline; new credentials default to session-only.');
})();
