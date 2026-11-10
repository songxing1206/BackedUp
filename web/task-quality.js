// Task completeness and provenance. These numbers are not semantic accuracy.
(function(root){
 function lines(task){
  const q=task?.evaluation,c=q?.counts;if(!q||!c)return [];
  const execution=q.execution_mode==='agent'?'单 Agent':'旧版执行',context={bm25:'BM25',bm25_neighbor:'BM25 + 邻近上下文',deep:'深度核查'}[q.context_mode]||(q.review_mode==='deep'?'深度核查':'BM25');
  return [
   `执行模式：${execution} · 上下文：${context}`,
   `本轮完成 ${c.completed}/${c.required} 处 · 来源待确认 ${c.source_unconfirmed} · 模型判断失败 ${c.model_failed}`,
   `无对应证据 ${c.no_evidence} · 原文未核实 ${c.evidence_unverified} · 定位失败 ${c.localization_failed} · 需人工复核 ${c.human_review}`,
   `模型请求 ${q.model_requests} 次 · 实际 Token ${q.total_tokens??'未返回'} · 耗时 ${q.duration_seconds??'—'} 秒`,
   '本摘要只检查完成度与证据可追溯性，不代表语义准确率。'
  ];
 }
 function render(task){
  const report=document.getElementById('report');if(!report)return;
  let panel=document.getElementById('task-quality');
  if(!panel){panel=document.createElement('section');panel.id='task-quality';panel.className='card';report.insertBefore(panel,report.querySelector('.report-controls'))}
  const content=lines(task);panel.hidden=!content.length;panel.replaceChildren();
  if(content.length){const heading=document.createElement('h2');heading.textContent='本轮结果质量检查';panel.append(heading);for(const line of content){const p=document.createElement('p');p.textContent=line;panel.append(p)}}
 }
 root.taskQualityLines=lines;root.renderTaskQuality=render;
 if(typeof module!=='undefined')module.exports={lines,render};
})(typeof window!=='undefined'?window:globalThis);
