const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('web/model-settings.js','utf8');const fn=src.slice(src.indexOf('async function updateModelStatus'),src.indexOf('function fillModelForm'));
const nodes={};function node(){return {textContent:'',classList:{toggle(k,v){this[k]=v}}}}
for(const id of ['model-state','model-indicator','model-indicator-title','model-indicator-detail'])nodes[id]=node();
let config={provider:'custom',model:'deepseek-chat',base_url:'https://models.sjtu.edu.cn/api/v1',has_key:true};
const c={modelConfig:{},$:id=>nodes[id],api:async()=>config};vm.createContext(c);vm.runInContext(fn,c);
(async()=>{await c.updateModelStatus();assert(nodes['model-indicator'].classList.configured);assert(nodes['model-indicator-detail'].textContent.includes('SJTU API'));config={...config,has_key:false};await c.updateModelStatus();assert(!nodes['model-indicator'].classList.configured);assert.equal(nodes['model-indicator-title'].textContent,'尚未配置模型');console.log('Model indicator configured/unconfigured passed')})().catch(e=>{console.error(e);process.exitCode=1});
