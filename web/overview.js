// Overview and history use final combined verdicts, never source identity as accuracy.
function overviewMetrics(record){
 record=record||{};
 const reviews=new Map((record.evidence_review?.locations||[]).map(r=>[r.location_id,r]));
 let reviewed=0,correct=0;const missing=new Set();
 for(const location of record.locations||[]){
  const r=reviews.get(location.id),members=location.members||[];
  if(r?.state==='complete'&&r.material_complete!==false&&members.every(m=>m.match.status==='matched')&&['支持','部分支持','不支持','存在矛盾'].includes(r.combined?.status)){reviewed++;if(r.combined.status==='支持')correct++}
  for(const m of members)if(['unmatched','missing_attachment'].includes(m.match.status))missing.add(m.match.source_id||`${m.author.toLowerCase().replace(/\s+/g,'')}|${m.year}`);
 }
 const total=(record.locations||[]).length;
 return {total,reviewed,correct,manual:total-reviewed,missing:missing.size,completion:total?Math.round(reviewed/total*100):null,accuracy:reviewed?Math.round(correct/reviewed*100):null};
}
let workspaceView='overview';
function checkPresentation(record,job,checking){
 const finished=!!record&&(!activeCheck||!!job&&job.task_id===record.id&&['completed','partial'].includes(job.status));
 return {overview:finished&&!checking,progress:!!job&&!['report','missing','identity'].includes(workspaceView)};
}
function syncCheckPresentation(){
 const state=checkPresentation(task,window.currentCheckJob,window.isChecking);
 $('overview').hidden=!state.overview||['report','missing','identity'].includes(workspaceView);
 $('check-progress').hidden=!state.progress;
 if(window.historyVisible)for(const id of ['input-view','overview','report','missing-view','identity-view','check-progress'])if($(id))$(id).hidden=true;
}
window.syncCheckPresentation=syncCheckPresentation;
function showWorkspaceView(view){
 setHistoryVisible(false);
 workspaceView=view;
 if($('identity-view'))$('identity-view').hidden=view!=='identity';
 syncCheckPresentation();
 $('input-view').hidden=['report','missing','identity'].includes(view);$('overview').hidden=['report','missing','identity'].includes(view)||!task;$('report').hidden=view!=='report'||!task;$('missing-view').hidden=view!=='missing';
 syncCheckPresentation();
 if(task)sessionData.setItem('backed-up-view-'+task.id,view);
 const target=$(view==='report'?'report':view==='missing'?'missing-view':'input-view');target.scrollIntoView({behavior:'smooth',block:'start'});
}
function metricCard(label,value,explanation,index){
 const card=el('button',undefined,'metric-card');card.type='button';card.setAttribute('aria-describedby','metric-tip-'+index);
 card.append(el('span',label,'metric-label'),el('strong',value));
 const tip=el('span',explanation,'metric-tip');tip.id='metric-tip-'+index;tip.setAttribute('role','tooltip');card.append(tip);
 card.onpointerleave=()=>card.classList.remove('tip-open');
 card.onclick=()=>{const open=!card.classList.contains('tip-open');document.querySelectorAll('.metric-card').forEach(n=>n.classList.remove('tip-open'));card.classList.toggle('tip-open',open)};
 return card;
}
function renderOverview(){
 if(!task)return;renderOriginalReview();const m=overviewMetrics(task),root=$('overview-metrics');root.replaceChildren();
 const title=task.text?.split('\n').find(line=>line.trim())?.trim().replace(/^#+\s*/,'')||'本次检查';$('overview-title').textContent=title.slice(0,80);
 $('overview-date').textContent=task.created_at?new Date(task.created_at).toLocaleString('zh-CN'):'';
 $('overview-state').textContent=window.isChecking?'检查中':m.total===0?'未识别到引用':m.manual?'部分完成':'检查完成';
 [
  ['检查完成率',m.completion===null?'—':m.completion+'%',`已审查 ${m.reviewed} 处 / 全文引用 ${m.total} 处。仅计入已完成且得出明确结论的引用位置。`],
  ['引用正确率',m.accuracy===null?'—':m.accuracy+'%',`引用正确 ${m.correct} 处 / 已审查 ${m.reviewed} 处。“支持”为正确；来源匹配本身不代表引用正确。`],
  ['待上传文献',m.missing+' 篇','全文引用中未找到来源或缺少可读 PDF 的文献，按作者与年份或已匹配来源去重；来源身份不确定归入需人工审查。'],
  ['需人工审查',m.manual+' 处','全文引用减去已审查的引用位置，包括检查未完成、来源不确定或无法下结论的项目。检查中尚未完成的项目也计入。']
 ].forEach((row,i)=>{const card=metricCard(...row,i);if(i===2){card.append(el('span','→','metric-arrow'));card.onclick=()=>{missingJobStarted=false;missingJobStatus='';missingRefreshed=false;missingUploadedCount=0;$('missing-status').textContent='';$('missing-uploaded').replaceChildren();renderMissing();showWorkspaceView('missing')}}root.append(card)});
 $('overview-counts').textContent=`引用正确 ${m.correct} 处 / 已审查 ${m.reviewed} 处 / 全文引用 ${m.total} 处`;
 syncCheckPresentation();
 // Polling updates numbers without interrupting the user's chosen report view.
 $('input-view').hidden=['report','missing','identity'].includes(workspaceView);$('overview').hidden=['report','missing','identity'].includes(workspaceView);$('report').hidden=workspaceView!=='report';$('missing-view').hidden=workspaceView!=='missing';
 syncCheckPresentation();
 if(workspaceView==='missing'){renderMissing();$('missing-check').disabled=!!window.isChecking||!missingUploadedCount;$('missing-files').disabled=!!window.isChecking;$('missing-status').textContent=window.isChecking?'正在检查补充文献的引用…':missingRefreshed?'已更新，请查看。':missingRefreshReady()?'本轮检查已结束，请刷新报告查看最新结论。':$('missing-status').textContent}
 if(!window.isChecking)history.replaceState(null,'','#task='+task.id);
}
window.resetOverview=()=>{$('overview').hidden=true;showWorkspaceView('input')};
$('see-report').onclick=()=>showWorkspaceView('report');$('back-overview').onclick=()=>showWorkspaceView('overview');
function setHistoryVisible(visible){
 window.historyVisible=visible;$('history-dialog').hidden=!visible;
 for(const [id,active] of [['precheck-open',!visible],['history-open',visible]]){const button=$(id);button?.classList?.toggle('active',active);button?.setAttribute?.('aria-pressed',String(active))}
 syncCheckPresentation();
}
$('precheck-open').onclick=()=>showWorkspaceView(task?'overview':'input');
$('history-open').onclick=async()=>{
 const list=$('history-list');list.replaceChildren(el('p','正在读取历史记录…','help'));setHistoryVisible(true);
 try{const records=await api('/api/history');list.replaceChildren();if(!records.length)list.append(el('p','暂无历史检查记录。','help'));
  for(const record of records){const m=overviewMetrics(record),button=el('button',undefined,'history-row');button.setAttribute('aria-disabled',String(!!window.isChecking));button.oncontextmenu=e=>historyContextMenu(e,record,button);
   button.append(el('strong',record.title),el('span',new Date(record.created_at).toLocaleString('zh-CN'),'help'),el('span',`${m.total===0?'未识别到引用':m.manual?'部分完成':'检查完成'} · 引用正确 ${m.correct} / 已审查 ${m.reviewed} / 全文引用 ${m.total}`,'help'));
   button.onclick=()=>{if(window.isChecking)return;if(!record.current){window.open(`/api/history/${record.namespace}/${record.id}/report`,'_blank','noopener');return}window.detachCheck?.();if(record.check_id)localData.setItem('backed-up-active-check',record.check_id);sessionData.setItem('backed-up-view-'+record.id,'overview');location.hash='task='+record.id;location.reload()};
   if(!record.current)button.append(el('span','旧格式历史 · 只读查看','help'));list.append(button)}
  if(window.isChecking)list.prepend(el('p','当前检查进行中，完成或取消后可打开历史报告。','help'));
 }catch(e){list.replaceChildren(el('p','历史记录读取失败：'+e.message,'help'))}
};
const previousNewCheck=$('new-check').onclick;$('new-check').onclick=()=>{previousNewCheck();if(!window.isChecking){saveDraft();showWorkspaceView('input')}};
const previousRun=$('run').onclick;$('run').onclick=()=>{workspaceView='overview';return previousRun()};
Promise.resolve(window.draftReady).then(()=>{if(task){workspaceView=sessionData.getItem('backed-up-view-'+task.id)||'overview';renderOverview()}else{$('overview').hidden=true;$('input-view').hidden=false}});

function originalReviewSegments(record){
 record=record||{};
 const text=record.text||'',reviews=new Map((record.evidence_review?.locations||[]).map(r=>[r.location_id,r]));
 const intervals=[];
 for(const loc of record.locations||[]){
  const review=reviews.get(loc.id),display=citationDisplayState(loc,review);
  if(display.color==='green')continue;
  // Backend offsets count Unicode code points; DOM strings count UTF-16 code units.
  const marker=Array.from(text).slice(0,loc.start).join('').length;
  let start=-1,at=0;
  while(loc.sentence&&(at=text.indexOf(loc.sentence,at))!==-1){if(at<=marker&&marker<at+loc.sentence.length){start=at;break}at++}
  let end;
  if(start>=0)end=start+loc.sentence.length;
  else{start=text.lastIndexOf('\n',marker)+1;end=text.indexOf('\n',marker);if(end<0)end=text.length}
  intervals.push({start,end,ids:[loc.id],color:display.color});
 }
 intervals.sort((a,b)=>a.start-b.start);const merged=[];
 const priority={gray:1,yellow:2,red:3};for(const interval of intervals){const last=merged[merged.length-1];if(last&&interval.start<last.end){last.end=Math.max(last.end,interval.end);last.ids.push(...interval.ids);if(priority[interval.color]>priority[last.color])last.color=interval.color}else merged.push({...interval})}
 const segments=[];let cursor=0;
 for(const interval of merged){if(interval.start>cursor)segments.push({text:text.slice(cursor,interval.start),ids:[]});segments.push({text:text.slice(interval.start,interval.end),ids:interval.ids,color:interval.color});cursor=interval.end}
 if(cursor<text.length)segments.push({text:text.slice(cursor),ids:[]});return segments;
}
function renderOriginalReview(){
 if(!task)return;const root=$('original-text'),issues=$('original-issues');root.replaceChildren();issues.replaceChildren();
 const ids=new Set();for(const segment of originalReviewSegments(task)){const span=el('span',segment.text,segment.ids.length?'original-result-'+segment.color:'');if(segment.ids.length){span.title=segment.ids.join('、')+'：'+({red:'存在明确问题',yellow:'部分支持',gray:'尚未可靠完成'}[segment.color]||'需复核');segment.ids.forEach(id=>ids.add(id))}root.append(span)}
 for(const loc of task.locations){const review=task.evidence_review?.locations.find(r=>r.location_id===loc.id),row=el('div',undefined,'original-action-row'),jump=el('button',loc.id,'original-location-link');jump.onclick=()=>jumpToCheckLocation(loc.id);const action=originalReviewAction(loc,review,task.check_errors||[]);row.append(jump,el('span',loc.members.map(m=>`${m.author} (${m.year})`).join('；')+' · '+action));issues.append(row)}
 $('original-retry').hidden=!activeCheck||!ids.size;$('original-retry').disabled=!!window.isChecking;
}
$('original-retry').onclick=async()=>{const button=$('original-retry');button.disabled=true;$('original-retry-status').textContent='正在准备补查…';await retryCheck();$('original-retry-status').textContent=$('retry-status').textContent;button.disabled=!!window.isChecking};

function originalReviewAction(loc,review,errors=[]){
 if(loc.members.some(m=>['unmatched','missing_attachment'].includes(m.match.status)))return '请上传或绑定对应 PDF 后重新检查。';
 if(loc.members.some(m=>m.match.status==='needs_assignment'))return '请在详细结果中确认实际对应的 PDF 后补查。';
 if(review?.state==='complete'&&review.material_complete!==false){
  if((review.claims||[]).some(c=>(c.source_judgments||[]).some(j=>(j.evidence||[]).some(e=>e.validation==='text_verified'&&e.location_state==='unmapped'))))return '原文已验证且引用结论保留；PDF 高亮不可用，请人工查看原文。';
  const status=review.combined?.status;
  if(status==='支持')return '引用获支持，无需补充材料。';
  if(status==='部分支持')return '仅部分支持，请核对论断的范围及限定条件。';
  if(['不支持','存在矛盾'].includes(status))return '引用不支持或存在矛盾，请核对原文并修正论断或引用。';
 }
 const message=errors.find(e=>new RegExp('^'+loc.id+'[:：]').test(e))||'';
 if(/字符范围|唯一映射|片段ID|摘录/.test(message))return '证据校验未完成，请先补查；仍失败时打开对应 PDF 人工核对。';
 return '检查尚未完成，请补查；仍无结论时核对对应 PDF。';
}

let missingTargets=[],missingJobStarted=false,missingUploadedCount=0,missingJobId=null,missingJobStatus='',missingRefreshed=false;
function missingRefreshReady(){return missingJobStarted&&missingJobId===activeCheck&&['completed','partial'].includes(missingJobStatus)}
window.updateMissingJob=job=>{if(job.id!==missingJobId)return;missingJobStatus=job.status;$('missing-refresh').disabled=!missingRefreshReady()};
function missingReferences(record){
 const rows=new Map();
 for(const loc of record.locations||[])for(const member of loc.members||[]){
  if(!['unmatched','missing_attachment'].includes(member.match.status))continue;
  const key=member.match.source_id||`${member.author.toLowerCase().replace(/\s+/g,'')}|${member.year}`;
  if(!rows.has(key))rows.set(key,{author:member.author,year:member.year,locations:[]});
  const row=rows.get(key);if(!row.locations.includes(loc.id))row.locations.push(loc.id);
 }
 return [...rows.values()];
}
function renderMissing(){
 if(!task)return;$('missing-refresh').disabled=!missingRefreshReady();$('missing-check').disabled=!!window.isChecking||!missingUploadedCount;const root=$('missing-list');root.replaceChildren();const rows=missingReferences(task);
 if(!missingJobStarted)missingTargets=[...new Set(rows.flatMap(r=>r.locations))];
 if(!rows.length)root.append(el('p','当前没有待上传文献。','help'));
 for(const row of rows){const item=el('div',undefined,'missing-reference');item.append(el('strong',`${row.author} (${row.year})`),el('span','对应引用：'+row.locations.join('、'),'help'));root.append(item)}
}
$('missing-home').onclick=()=>showWorkspaceView('overview');
$('missing-files').onchange=async e=>{
 const files=Array.from(e.target.files);e.target.value='';if(!files.length||window.isChecking)return;
 missingJobStarted=false;missingJobStatus='';missingRefreshed=false;$('missing-refresh').disabled=true;$('missing-status').textContent='';const button=$('missing-check');button.disabled=true;$('missing-files').disabled=true;let success=0,duplicates=0,failed=0;
 const known=new Set();for(const s of sources){const hash=await pdfHash(s);if(hash)known.add(hash)}
 try{for(const [i,file] of files.entries()){
  $('missing-upload-status').textContent=`正在上传 ${i+1}/${files.length}：${file.name}`;
  try{
   if(!/\.pdf$/i.test(file.name))throw Error('请选择 PDF 文件');if(file.size>15*1024*1024)throw Error('文件超过 15 MB');
   const bytes=await file.arrayBuffer(),hash=await digest(bytes);if(known.has(hash)){duplicates++;continue}
   const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file)});
   const source=await api('/api/assets',{name:file.name,data});sources.push(source);known.add(hash);success++;missingUploadedCount++;
   $('missing-uploaded').append(el('p',file.name+' · 上传成功，待检查','help'));
  }catch(error){failed++;$('missing-uploaded').append(el('p',file.name+' · '+error.message,'missing-error'))}
 }
 renderSources();saveDraft();$('missing-upload-status').textContent=`上传完成：新增 ${success} 篇，跳过重复 ${duplicates} 篇，失败 ${failed} 篇`;
 }finally{button.disabled=!missingUploadedCount;$('missing-files').disabled=false}
};
$('missing-check').onclick=async()=>{
 if(window.isChecking)return;const button=$('missing-check');button.disabled=true;
 try{
  if(!task||!missingTargets.length)throw Error('当前没有需要补充检查的引用');
  await updateModelStatus();if(!modelConfig.provider||(!['codex','claude'].includes(modelConfig.provider)&&!modelConfig.has_key)){openModelSettings();throw Error('请连接审查模型后检查')}
  $('missing-status').textContent='正在启动补充检查…';
  const job=await api('/api/checks',{text:task.text,source_ids:sources.map(s=>s.id),task_id:task.id,location_ids:missingTargets,retry_failed_requests:true});
  missingJobStarted=true;missingJobId=job.id;missingJobStatus=job.status;missingRefreshed=false;activeCheck=job.id;localData.setItem('backed-up-active-check',activeCheck);showJob(job);clearTimeout(pollTimer);await pollCheck();
 }catch(error){$('missing-status').textContent='检查未启动：'+error.message}finally{button.disabled=!!window.isChecking}
};
$('missing-refresh').onclick=()=>work($('missing-refresh'),async()=>{
 if(!task||!missingRefreshReady())return;task=await api('/api/tasks/'+task.id);sources=await uniqueSources([...task.sources,...sources]);renderSources();report();renderMissing();missingRefreshed=true;$('missing-status').textContent='已更新，请查看。';
});

let identitySource=null,identityTargets=[];
function openIdentityPage(message){
 let page=$('identity-view');if(!page){page=el('section',undefined,'card');page.id='identity-view';$('input-view').after(page)}
 page.hidden=false;showWorkspaceView('identity');page.replaceChildren();identityTargets=[];
 const home=el('button','← 返回主页');home.onclick=()=>{page.hidden=true;showWorkspaceView('overview')};page.append(home,el('h2','补充作者与年份'),el('p','打开 PDF 确认参考文献信息，填写该文献在论文中引用的作者与年份。'));
 const select=el('select');select.setAttribute('aria-label','选择对应 PDF');const filename=message.split(/[:：]/)[0];
 for(const source of sources){const option=el('option',source.filename||source.title||source.id);option.value=source.id;option.selected=source.filename===filename;select.append(option)}
 const author=el('input'),year=el('input');author.placeholder='作者 / 第一作者姓氏';author.setAttribute('aria-label','作者');year.placeholder='年份，例如 2022';year.setAttribute('aria-label','年份');
 const pdf=el('a','打开 PDF ↗');pdf.target='_blank';pdf.rel='noopener';
 const feedback=el('p');feedback.setAttribute('role','status');const confirm=el('button','确认匹配'),check=el('button','仅校验这篇文献');check.disabled=true;
 function changed(){identitySource=sources.find(s=>s.id===select.value);author.value=identitySource?.authors||'';year.value=identitySource?.year||'';pdf.href='/api/assets/'+select.value+'/pdf';identityTargets=[];check.disabled=true;feedback.textContent=''}
 select.onchange=changed;for(const input of [author,year])input.oninput=()=>{identityTargets=[];check.disabled=true;feedback.textContent=''};changed();
 confirm.onclick=async()=>{confirm.disabled=true;check.disabled=true;identityTargets=[];try{const result=await api('/api/tasks/'+task.id+'/source-identity',{source_id:select.value,authors:author.value,year:year.value});task=result.task;sources=task.sources;identityTargets=result.location_ids;feedback.textContent=result.matched?'匹配成功：'+identityTargets.join('、')+'。请点击仅校验这篇文献。':'存在同作者同年份的多个候选，请在报告中手动指定来源。';check.disabled=!result.matched;renderSources();renderOverview()}catch(error){feedback.textContent=error.message}finally{confirm.disabled=false}};
 check.onclick=async()=>{if(window.isChecking||!identityTargets.length)return;check.disabled=true;try{const job=await api('/api/checks',{text:task.text,source_ids:sources.map(s=>s.id),task_id:task.id,location_ids:identityTargets});activeCheck=job.id;localData.setItem('backed-up-active-check',activeCheck);page.hidden=true;showWorkspaceView('overview');showJob(job);clearTimeout(pollTimer);await pollCheck()}catch(error){feedback.textContent=error.message;check.disabled=false}};
 page.append(select,pdf,author,year,confirm,check,feedback);page.scrollIntoView({behavior:'smooth',block:'start'});
}

let historyMenu;
function closeHistoryMenu(){historyMenu?.remove();historyMenu=null}
function historyContextMenu(event,record,row){
 event.preventDefault();closeHistoryMenu();
 const menu=el('div',undefined,'history-context-menu');historyMenu=menu;menu.setAttribute('role','menu');
 const remove=el('button',record.is_checking?'正在检查，请稍后':'删除记录');remove.setAttribute('role','menuitem');remove.disabled=!!record.is_checking;menu.append(remove);
 menu.style.left=Math.max(8,Math.min(event.clientX,window.innerWidth-220))+'px';menu.style.top=Math.max(8,Math.min(event.clientY,window.innerHeight-70))+'px';
 remove.onclick=async()=>{
  closeHistoryMenu();if(!await confirmHistoryDelete())return;
  try{await api(`/api/history/${record.namespace}/${record.id}/delete`,{});
   if(task?.id===record.id){reset();history.replaceState(null,'',location.pathname)}
   if(localData.getItem('backed-up-active-check')===record.check_id)localData.removeItem('backed-up-active-check');
   sessionData.removeItem('backed-up-view-'+record.id);row.remove();setHistoryVisible(true);showHistoryDeleted();
   if(!$('history-list').children.length)$('history-list').append(el('p','暂无历史检查记录。','help'));
  }catch(e){alert(e.message)}
 };document.body.append(menu);remove.focus();
}
document.addEventListener('pointerdown',e=>{if(historyMenu&&!historyMenu.contains(e.target))closeHistoryMenu()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeHistoryMenu()});
window.addEventListener('scroll',closeHistoryMenu,true);

function confirmHistoryDelete(){
 return new Promise(resolve=>{
  const dialog=el('dialog',undefined,'history-delete-dialog');dialog.setAttribute('aria-labelledby','history-delete-title');
  const title=el('h2','Backed Up 提示');title.id='history-delete-title';
  const message=el('p','确认删除这条历史记录及对应报告？此操作无法撤销。');
  const actions=el('div',undefined,'history-delete-actions'),cancel=el('button','取消'),confirm=el('button','删除');
  let settled=false;function finish(value){if(settled)return;settled=true;dialog.close();dialog.remove();resolve(value)}
  cancel.onclick=()=>finish(false);confirm.onclick=()=>finish(true);dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false)});
  actions.append(cancel,confirm);dialog.append(title,message,actions);document.body.append(dialog);dialog.showModal();cancel.focus();
 });
}

let historyDeletedTimer;
function showHistoryDeleted(){
 clearTimeout(historyDeletedTimer);
 let toast=$('history-deleted-toast');
 if(!toast){toast=el('div',undefined,'history-deleted-toast');toast.id='history-deleted-toast';toast.setAttribute('role','status');toast.setAttribute('aria-live','polite');document.body.append(toast)}
 toast.textContent='✓ 已删除';toast.hidden=false;
 historyDeletedTimer=setTimeout(()=>{toast.hidden=true},2000);
}
