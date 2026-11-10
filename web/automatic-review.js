function checkErrorAdvice(message){
 if(/书目信息不完整|书目信息尚未确认|书目依据不是原文|书目字段缺少/.test(message))return {title:'文献信息缺失，尚无法确认来源',next:'需要用户打开 PDF 并确认参考文献信息，补充对应论文中的（作者，年份）信息。',action:'metadata'};
 if(/预算|处理上限|上下文.*超过|系统无法.*请求|系统无法合并/.test(message))return {title:'系统分批处理未完成，此处检查失败',next:'这不是 API 余额不足，也不能据此判断模型不支持。请点击补查未完成项，使用更新后的自动分批处理；若仍失败，请保留技术详情供排查。',action:'budget'};
 if(/字符范围|唯一映射|片段ID|摘录与真实原文|证据定位失败/.test(message))return {title:'参考文献证据定位失败',next:'重新定位证据；仍失败时，打开参考文献 PDF 人工核对。本次暂无法完成引用判断，不代表引用错误。',action:'retry'};
 if(/截断|JSON/.test(message))return {title:'模型未返回完整结果，此处尚无法判断',next:'先补查；若仍失败，在模型连接中更换模型后再次补查。此前完成的结果会保留。',action:'retry'};
 return {title:'检查未完成，此处尚无法判断',next:'先查看下方技术详情并补查；若仍失败，请保留报错信息以便排查。',action:'retry'};
}
function jumpToCheckLocation(id,preserveFilter=false){
 const node=document.getElementById('citation-'+id);if(!node)return;
 window.showWorkspaceView?.('report');if(!preserveFilter)$('result-filter').value='all';filterResults();node.scrollIntoView({behavior:'smooth',block:'start'});
}
function checkSummaryRows(record,job){
 record=record||{};job=job||{status:'queued',errors:[]};
 const reviews=new Map((record.evidence_review?.locations||[]).map(r=>[r.location_id,r]));
 const selected=(record.locations||[]).filter(loc=>!job.location_ids||job.location_ids.includes(loc.id));
 return (job.location_limit?selected.slice(0,job.location_limit):selected).map((loc,index)=>{
  if(['queued','running'].includes(job.status)&&index>=job.completed)return {id:loc.id,text:job.stage?.includes(loc.id)?'正在检查':'等待检查',ok:false};
  const errors=(job.errors||[]).filter(message=>message.startsWith(loc.id+'：')||message.startsWith(loc.id+':'));
  const review=reviews.get(loc.id);
  if(errors.length){const advice=checkErrorAdvice(errors[0]);return {id:loc.id,text:advice.title+'。建议：'+advice.next,ok:false}}
  const unresolved=loc.members.some(m=>m.match.status!=='matched');
  if(loc.members.some(m=>m.match.status==='missing_attachment'))return {id:loc.id,text:'参考文献 PDF 缺失或不可读。建议：补充可读取的 PDF 后再补查。',ok:false};
  if(unresolved)return {id:loc.id,text:'文献信息缺失，尚无法确认来源。建议：打开 PDF，补充并确认作者、年份及对应引用。',ok:false};
  if(review?.state==='complete'&&review.material_complete!==false&&['支持','部分支持','不支持','存在矛盾'].includes(review.combined?.status))return {id:loc.id,text:'已成功检查',ok:true};
  const failed=(review?.claims||[]).some(c=>c.source_judgments.some(j=>j.verification_error));
  return {id:loc.id,text:failed?'参考文献证据定位失败。建议：打开 PDF 人工核对，或补查此处引用。':'尚未完成检查。建议：查看对应报告并补查未完成项。',ok:false};
 });
}
function renderCompactCheckSummary(record,job){
 const root=$('check-errors');root.replaceChildren();
 for(const row of checkSummaryRows(record,job)){
  const line=el('div',undefined,'check-summary-line'+(row.ok?' check-summary-success':''));
  const link=el('button',row.id,'check-summary-link');link.title='点击查看引用详情；已成功检查不代表引用一定正确';link.onclick=()=>jumpToCheckLocation(row.id);
  const content=el('div',undefined,'check-summary-content'),split=row.text.indexOf('建议：');
  content.append(el('span','：'+(split<0?row.text:row.text.slice(0,split).trim())));
  if(split>=0)content.append(el('div',row.text.slice(split),'check-summary-advice'));
  line.append(link,content);root.append(line);
 }
 root.hidden=false;
 const unmatchedErrors=(job.errors||[]).filter(message=>!/^C\d+[：:]/.test(message));
 if(/第\d\/2轮/.test(job.stage||''))unmatchedErrors.push('内部处理阶段：'+job.stage);
 if(unmatchedErrors.length){const details=el('details',undefined,'check-summary-details');details.append(el('summary','其他处理信息（'+unmatchedErrors.length+'）'));for(const message of unmatchedErrors)details.append(el('p',message));root.append(details)}
}
function renderCheckErrors(job){
 if(typeof task!=='undefined'&&task?.id===job.task_id){renderCompactCheckSummary(task,job);return}
 const root=$('check-errors');root.replaceChildren();root.hidden=!(job.errors||[]).length;
 if(!root.hidden){const details=el('details');details.append(el('summary','处理信息（'+job.errors.length+'）'));for(const message of job.errors)details.append(el('p',message));root.append(details)}
}
function resetCheckFeedback(){
 clearTimeout(pollTimer);requestEpoch++;
 $('check-progress').hidden=false;$('check-stage').textContent='正在准备重新检查…';$('check-count').textContent='等待开始';
 $('check-errors').replaceChildren();$('check-errors').hidden=true;
 if(typeof task!=='undefined'&&task)renderCompactCheckSummary(task,{status:'queued',task_id:task.id,completed:0,errors:[]});
}
function userCheckStage(job){
 const found=String(job.stage||'').match(/检索证据核查 (C\d+) · 第(\d)\/2轮/);
 if(found)return found[2]==='1'?'正在检查 '+found[1]:'正在补充 '+found[1]+' 的证据';
 return job.status==='completed'?'本轮检查已完成':job.status==='partial'?'本轮检查未全部完成':job.stage;
}
function lockCheckInputs(){const active=!!window.isChecking;$('text').readOnly=active;for(const id of ['pdf-files','folder-files','manuscript-file','bib-file','new-check','review-mode','token-budget','request-budget'])$(id).disabled=active||!!window.isUploading;for(const b of document.querySelectorAll('#sources input,#sources button,#results .assignment button'))b.disabled=active}
let activeCheck=null,pollTimer,requestEpoch=0;
window.detachCheck=function(){activeCheck=null;window.currentCheckJob=null;localData.removeItem('backed-up-active-check');clearTimeout(pollTimer);requestEpoch++;$('check-progress').hidden=true};
function showJob(job){window.currentCheckJob=job;window.updateMissingJob?.(job);window.isChecking=['queued','running'].includes(job.status);lockCheckInputs();$('run').textContent=window.isChecking?'检查中':'开始检查 →';$('check-progress').hidden=!window.isChecking;$('check-stage').textContent=userCheckStage(job);const context={bm25:'BM25',bm25_neighbor:'BM25 + 邻近上下文',deep:'深度核查'}[job.context_mode]||(job.review_mode==='deep'?'深度核查':'BM25');$('check-count').textContent=`${job.completed} / ${job.total||'—'} 个引用位置已处理 · ${job.execution_mode==='legacy'?'旧版执行':'单 Agent'} · ${context} · 模型请求 ${job.budget_usage?.requests||0} 次 · 实际 Token ${job.budget_usage?.actual_tokens??'未返回'}`;renderCheckErrors(job);$('cancel-check').hidden=!['queued','running'].includes(job.status);$('retry-check').hidden=['queued','running','completed'].includes(job.status);$('retry-description').hidden=$('retry-check').hidden;$('run').disabled=['queued','running'].includes(job.status);window.syncCheckPresentation?.()}
async function pollCheck(){const epoch=++requestEpoch,id=activeCheck;if(!id)return;try{let job=await api('/api/checks/'+id);if(epoch!==requestEpoch)return;showJob(job);if(job.task_id){const loaded=await api('/api/tasks/'+job.task_id);if(epoch!==requestEpoch)return;task=loaded;task.check_errors=job.errors||[];renderCheckErrors(job);report();$('report-info').textContent=`${task.summary.locations} 个引用位置 · ${task.summary.members} 条文献标记 · ${userCheckStage(job)}`;if(task.sources)sources=task.sources;renderSources();lockCheckInputs()}if(['queued','running'].includes(job.status))pollTimer=setTimeout(pollCheck,1500);else{$('run').disabled=false;saveDraft()}}catch(e){if(epoch!==requestEpoch)return;$('error').textContent=e.message;$('error').hidden=false;$('run').disabled=false}}
let acknowledgedPreflight='';
function preflightAction(issue){const actions={upload_pdf:['上传缺失 PDF',()=>$('pdf-files').click()],replace_pdf:['替换 PDF',()=>$('pdf-files').click()],review_uploaded:['核对已上传 PDF',()=>document.getElementById('sources')?.scrollIntoView({behavior:'smooth'})],select_candidate:['选择候选来源',()=>document.getElementById('sources')?.scrollIntoView({behavior:'smooth'})],resolve_identity:['核对身份信息',()=>document.getElementById('sources')?.scrollIntoView({behavior:'smooth'})]};return actions[issue.action]}
$('run').onclick=()=>work($('run'),async()=>{if(!$('text').value.trim())throw Error('请输入稿件');if(!sources.length)throw Error('请上传 PDF');const preflight=await api('/api/checks/preflight',{text:$('text').value,source_ids:sources.map(s=>s.id)});const preflightKey=JSON.stringify([$('text').value,sources.map(s=>s.id),preflight]);const panel=$('source-preflight');panel.replaceChildren();if(preflight.issues.length){const title=document.createElement('p');title.textContent='来源预检查（未调用模型）：以下问题可能影响判断。';panel.append(title);for(const issue of preflight.issues){const line=document.createElement('p');line.textContent=issue.label+'：'+issue.message+'。'+issue.advice;const action=preflightAction(issue);if(action){const button=document.createElement('button');button.textContent=action[0];button.className='outline preflight-action';button.onclick=action[1];line.append(button)}panel.append(line)}panel.hidden=false;if(!preflight.readable_files){acknowledgedPreflight='';throw Error('没有可读取的 PDF，请先替换或补充文件')}if(acknowledgedPreflight!==preflightKey){acknowledgedPreflight=preflightKey;$('check-progress').hidden=true;$('run').textContent='继续检查可用来源';panel.scrollIntoView({behavior:'smooth',block:'center'});return}}else{panel.hidden=true;acknowledgedPreflight=''}await updateModelStatus();if(!modelConfig.provider||!modelConfig.has_key){openModelSettings();throw Error('请先连接审查模型，再开始检查')}if(typeof resetCheckFeedback==='function')resetCheckFeedback();$('run').textContent='开始检查 →';showJob({status:'queued',stage:'正在启动本轮检查…',completed:0,total:0});let job;try{job=await api('/api/checks',{text:$('text').value,source_ids:sources.map(s=>s.id),review_mode:$('review-mode').value,max_requests:$('request-budget').value?Number($('request-budget').value):null,token_budget:$('token-budget').value?Number($('token-budget').value):null,retry_failed_requests:typeof task!=='undefined'&&!!task})}catch(e){showJob({status:'failed',stage:'检查未启动：'+e.message,completed:0,total:0});throw e}activeCheck=job.id;localData.setItem('backed-up-active-check',activeCheck);showJob(job);clearTimeout(pollTimer);await pollCheck()});$('cancel-check').onclick=()=>work($('cancel-check'),async()=>{await api('/api/checks/'+activeCheck+'/cancel',{});await pollCheck()});async function retryCheck(){const button=$('retry-check'),status=$('retry-status');button.disabled=true;button.textContent='正在准备补查…';if(typeof resetCheckFeedback==='function')resetCheckFeedback();status.textContent='正在检查模型连接…';try{await updateModelStatus();if(!modelConfig.provider||!modelConfig.has_key){status.textContent='尚未连接审查模型或会话 Key 已失效。请重新配置模型，保存后再次点击重试。';openModelSettings();return}if(!activeCheck)throw Error('没有可补查的检查任务，请重新打开原检查报告。');status.textContent='正在提交补查，保留此前已完成结果…';const job=await api('/api/checks/'+activeCheck+'/retry',{max_requests:$('request-budget').value?Number($('request-budget').value):null,token_budget:$('token-budget').value?Number($('token-budget').value):null});activeCheck=job.id;localData.setItem('backed-up-active-check',activeCheck);showJob(job);status.textContent='补查已启动，正在处理未完成项。';clearTimeout(pollTimer);await pollCheck()}catch(e){status.textContent='补查未启动：'+e.message}finally{button.textContent='重试未完成项';button.disabled=!!window.isChecking}}
$('retry-check').onclick=retryCheck;
function reportMarkdown(){let lines=['# 引文有据检查报告','',...(window.taskQualityLines?.(task)||[]),''];for(const l of task.locations){const r=task.evidence_review?.locations.find(r=>r.location_id===l.id),elapsed=Number.isFinite(r?.processing_seconds)?r.processing_seconds+' 秒':'未记录';lines.push('## '+l.id,l.sentence,'','处理耗时：'+elapsed,...l.members.map(m=>`${m.author} (${m.year})：${labels[m.match.status]} — ${m.match.reason}`),'综合结论：'+(r?.combined.status||'无法判断')+' — '+(r?.combined.reason||'尚未核查'));for(const c of r?.claims||[])for(const j of c.source_judgments){const s=task.sources.find(s=>s.id===j.source_id);lines.push(`${s?.title||j.source_id}：${j.status} — ${j.reason}`);for(const e of j.evidence)lines.push(`> ${e.quote}\n\n${e.regions?.length?'物理第 '+e.regions[0].physical_page+' 页':'无法精准定位'}；原文已校验`)}if(r?.suggestion)lines.push('修改建议：'+r.suggestion.text)}return lines.join('\n\n')}
$('export-md').onclick=()=>{if(!task)return;const a=el('a');a.href=URL.createObjectURL(new Blob([reportMarkdown()],{type:'text/markdown;charset=utf-8'}));a.download='引文有据检查报告.md';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
function filterResults(){const problems=$('result-filter').value==='problems';for(const article of document.querySelectorAll('#results .evidence-location')){const location=task?.locations.find(l=>'citation-'+l.id===article.id),review=task?.evidence_review?.locations.find(r=>r.location_id===location?.id);article.hidden=problems&&!!location&&citationNavigationState(location,review).color==='green'}renderCitationNav()}$('result-filter').onchange=filterResults;
function applySuggestion(loc,suggestion){if(!suggestion?.verified)return;const original=task.locations.find(l=>l.id===loc.location_id);if(!original)return;const text=$('text').value,first=text.indexOf(original.sentence);if(first<0||text.indexOf(original.sentence,first+1)>=0){$('error').hidden=false;$('error').textContent='原句不唯一或已修改，请手动编辑后检查';return}localData.setItem('backed-up-undo-text',text);$('text').value=text.slice(0,first)+suggestion.text+text.slice(first+original.sentence.length);window.detachCheck();saveDraft();$('undo-edit').hidden=false;$('edit-notice').textContent='已采用建议，请点击“开始检查”验证修改后的正文。';}
$('undo-edit').onclick=()=>{const previous=localData.getItem('backed-up-undo-text');if(previous!==null){$('text').value=previous;localData.removeItem('backed-up-undo-text');window.detachCheck();saveDraft();$('undo-edit').hidden=true;$('edit-notice').textContent='已撤销修改';}};
Promise.resolve(window.draftReady).then(()=>{activeCheck=localData.getItem('backed-up-active-check');if(activeCheck)pollCheck()});

$('new-check').onclick=()=>{if(window.isChecking||window.isUploading)return;reset();acknowledgedPreflight='';$('source-preflight').hidden=true;$('source-preflight').replaceChildren?.();$('run').textContent='开始检查 →';sources=[];$('text').value='';$('error').hidden=true;$('upload-status').textContent='';$('upload-errors').hidden=true;$('upload-errors').replaceChildren?.();$('edit-notice').textContent='';$('undo-edit').hidden=true;renderSources();history.replaceState(null,'',location.pathname);};

function citationNavigationState(location,review){
 return citationDisplayState(location,review);
}
function renderCitationNav(){
 const nav=$('citation-nav');if(!nav||!task)return;nav.replaceChildren();nav.append(el('strong','快速定位'),el('p','绿：支持  红：不支持/矛盾/确认年份错误  黄：部分支持  灰：未可靠完成','nav-legend'));
 const list=el('div',undefined,'citation-nav-list');
 for(const location of task.locations){const review=task.evidence_review?.locations.find(r=>r.location_id===location.id),state=citationNavigationState(location,review);if($('result-filter').value==='problems'&&state.color==='green')continue;const button=el('button',location.id,'citation-nav-item '+state.color);button.dataset.location=location.id;button.title=location.id+' · '+state.label;button.setAttribute('aria-label',button.title);button.onclick=()=>jumpToCheckLocation(location.id,true);list.append(button)}
 nav.append(list);updateCitationNavActive();
}
function updateCitationNavActive(){
 const cards=[...document.querySelectorAll('#results .evidence-location')].filter(n=>!n.hidden);if(!cards.length)return;
 const current=cards.find(n=>n.getBoundingClientRect().bottom>80)||cards[cards.length-1];
 for(const button of document.querySelectorAll('.citation-nav-item')){const active='citation-'+button.dataset.location===current.id;button.classList.toggle('current',active);if(active)button.setAttribute('aria-current','location');else button.removeAttribute('aria-current')}
}
let navFrame=false;window.addEventListener('scroll',()=>{if(navFrame)return;navFrame=true;requestAnimationFrame(()=>{navFrame=false;updateCitationNavActive()})},{passive:true});

function updateReviewEstimate(){
 const deep=$('review-mode')?.value==='deep',node=$('review-estimate');if(!node)return;
 node.textContent=deep?'默认检查全部引用；深度核查会分块发送全文，调用量取决于文献长度。可用 Token 与请求上限控制消耗。':'默认检查全部引用；每处通常判定1—2次，书目首次解析另计。当前来源 '+sources.length+' 篇。';
}
if($('review-mode'))$('review-mode').addEventListener('change',updateReviewEstimate);
