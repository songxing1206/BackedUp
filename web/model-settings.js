let modelConfig={};
async function updateModelStatus(){modelConfig=await api('/api/model/settings');$('model-state').textContent=modelConfig.provider?(modelConfig.provider+' · '+(modelConfig.model||'未配置模型')):'尚未连接模型';const indicator=$('model-indicator');if(indicator){const ready=!!(modelConfig.provider&&modelConfig.has_key);indicator.classList.toggle('configured',ready);$('model-indicator-title').textContent=ready?'模型已配置':'尚未配置模型';$('model-indicator-detail').textContent=ready?(modelConfig.model+' · '+(String(modelConfig.base_url||'').includes('models.sjtu.edu.cn')?'SJTU API':modelConfig.provider+' API')):'请连接您的模型 API';indicator.title=ready?'已配置模型与 API Key；不代表本次网络连接已经测试通过':'请连接模型并填写 API Key'}}
function fillModelForm(){const c=modelConfig,supported=['deepseek','openai','google','anthropic','custom'].includes(c.provider);$('model-provider').value=supported?c.provider:'custom';$('model-id').value=supported?(c.model||'deepseek-chat'):'deepseek-chat';$('model-url').value=supported?(c.base_url||'https://models.sjtu.edu.cn/api/v1'):'https://models.sjtu.edu.cn/api/v1';$('model-key').value='';$('model-key').placeholder=c.has_key?'已保存；留空保留现有 Key':'填写 API Key';$('model-session').checked=c.session_only!==false;$('reasoning-effort').value=c.reasoning_effort||'high';$('reasoning-output').value=String(c.reasoning_output_tokens||32768);$('reasoning-timeout').value=String(c.reasoning_timeout_seconds||1800);modelFormMode()}
function modelFormMode(){const p=$('model-provider').value;const defaults={google:'https://generativelanguage.googleapis.com/v1beta/openai',deepseek:'https://api.deepseek.com',openai:'https://api.openai.com/v1',anthropic:'https://api.anthropic.com/v1'};if(!$('model-url').value)$('model-url').value=defaults[p]||'';$('api-options').hidden=false;$('model-id').placeholder=p==='google'?'填写 Google AI Studio 中可用的 Gemini 模型 ID':'填写服务商当前提供的模型 ID';if(p==='google'&&!modelConfig.has_key)$('model-key').placeholder='填写 Google AI Studio 的 Gemini API Key';campusModelHint()}
function campusModelHint(defaultModel=false){const campus=$('model-url').value.trim().replace(/\/+$/,'')==='https://models.sjtu.edu.cn/api/v1';$('model-mode-help').hidden=!campus;$('reasoning-options').hidden=$('model-id').value.trim().toLowerCase()!=='deepseek-reasoner'}
function openModelSettings(){fillModelForm();campusModelHint();$('model-dialog').showModal()}
$('model-open').onclick=async()=>{
 openModelSettings();$('model-feedback').textContent='正在读取连接配置…';
 try{const config=await api('/api/config');token=config.token;await updateModelStatus();fillModelForm();$('model-feedback').textContent=''}
 catch(error){$('model-feedback').textContent='无法连接本地服务，请确认服务已启动后重试。模型测试尚未发起。'}
};$('model-close').onclick=()=>$('model-dialog').close();$('model-provider').onchange=()=>{const defaults={google:'https://generativelanguage.googleapis.com/v1beta/openai',deepseek:'https://api.deepseek.com',openai:'https://api.openai.com/v1',anthropic:'https://api.anthropic.com/v1'};$('model-url').value=defaults[$('model-provider').value]||'';$('model-key').value='';$('model-id').value='';modelFormMode()};
async function saveModel(clear=false){const body={provider:$('model-provider').value,model:$('model-id').value,base_url:$('model-url').value,api_key:$('model-key').value,session_only:$('model-session').checked,reasoning_effort:$('reasoning-effort').value||'high',reasoning_output_tokens:Number($('reasoning-output').value||32768),reasoning_timeout_seconds:Number($('reasoning-timeout').value||1800),clear_key:clear};modelConfig=await api('/api/model/settings',body);$('model-key').value='';await updateModelStatus();fillModelForm()}
$('model-save').onclick=()=>work($('model-save'),async()=>{await saveModel();$('model-feedback').textContent='连接配置已保存。开始检查时会把稿件及文献文字发送给该模型服务。';$('model-dialog').close()});$('model-test').onclick=async()=>{
 const button=$('model-test');if(button.disabled)return;
 button.disabled=true;button.textContent='测试中…';$('model-save').disabled=true;$('model-clear').disabled=true;
 const controller=new AbortController();let expired=false;
 const timer=setTimeout(()=>{expired=true;controller.abort()},135000);
 try{
  $('model-feedback').textContent='正在测试连接，请稍候…';
  await saveModel();
  const response=await fetch('/api/model/test',{method:'POST',headers:{'Content-Type':'application/json','X-BackedUp-Token':token},body:JSON.stringify({provider:modelConfig.provider,model:modelConfig.model,base_url:modelConfig.base_url}),signal:controller.signal});
  const result=await response.json();if(!response.ok)throw Error(result.error||'连接测试失败');
  $('model-feedback').textContent='连接测试成功';
 }catch(error){$('model-feedback').textContent=expired?'连接测试等待超时。请检查网络后重试；本次未取得连接结果。':'连接测试失败：'+error.message}
 finally{clearTimeout(timer);button.disabled=false;button.textContent='测试连接';$('model-save').disabled=false;$('model-clear').disabled=false}
};$('model-clear').onclick=()=>work($('model-clear'),async()=>{await saveModel(true);$('model-feedback').textContent='API Key 已清除'});
api('/api/config').then(c=>{token=c.token;return updateModelStatus()}).catch(()=>{});

for(const id of ['model-id','model-key','model-url'])$(id).addEventListener('input',()=>{campusModelHint(id==='model-url');$('model-feedback').textContent='配置已修改，请重新测试连接'});
