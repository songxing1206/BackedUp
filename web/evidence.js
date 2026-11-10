// Four-color presentation is derived from, but never written back into, semantic labels.
function verifiedEvidence(judgment){return (judgment?.evidence||[]).filter(e=>['verified','text_verified'].includes(e.validation))}
function judgmentDisplayState(judgment){
 if(!judgment||judgment.status==='无法判断')return {color:'gray',label:'未可靠完成',issues:[]};
 // Full-text non-support may be an absence finding with a concrete reason and
 // no positive quote. Support, partial support and contradiction still need
 // independently verified source text.
 if(['支持','部分支持','存在矛盾'].includes(judgment.status)&&!verifiedEvidence(judgment).length)return {color:'gray',label:'原文未验证',issues:['证据未验证']};
 const issues=(judgment.issue_types||[]).slice();
 if(judgment.status==='支持')return {color:'green',label:'语义支持',issues};
 if(judgment.status==='部分支持')return {color:'yellow',label:'部分支持',issues:issues.length?issues:['部分主张/过度概括']};
 if(judgment.status==='不支持')return {color:'red',label:'原文不支持',issues:issues.length?issues:['原文不支持']};
 return {color:'red',label:'存在矛盾',issues:issues.length?issues:['实质矛盾']};
}
function citationDisplayState(location,review){
 const members=location?.members||[],confirmedYear=members.find(m=>m.match?.year_diagnosis?.status==='confirmed_error');
 if(confirmedYear)return {color:'red',label:'引用年份错误',issues:['引用年份'],reason:confirmedYear.match.year_diagnosis.reason};
 const mismatchedYear=members.find(m=>m.match?.year_diagnosis?.status==='mismatch');
 if(mismatchedYear)return {color:'red',label:'引用年份/PDF 不匹配',issues:['引用年份或来源文件'],reason:mismatchedYear.match.year_diagnosis.reason};
 if(members.some(m=>m.match?.status!=='matched')){const d=grayDiagnostic(location,review);return {color:'gray',label:d.label,issues:[d.stage]}}
 if(!review||review.state!=='complete'){const d=grayDiagnostic(location,review);return {color:'gray',label:d.label,issues:[d.stage]}}
 const judgments=(review.claims||[]).flatMap(c=>c.source_judgments||[]),states=judgments.map(judgmentDisplayState);
 const combined=review.combined?.status;
 const issues=[...new Set(states.flatMap(s=>s.issues))];
 // Preserve an explicit partial-support result when at least one contributing
 // judgment has verified text. An unfinished sibling is disclosed instead of
 // erasing the completed yellow result. Missing/unmatched sources were already
 // rejected above and remain gray.
 const verifiedJudgment=judgments.some(j=>['支持','部分支持','不支持','存在矛盾'].includes(j.status)&&(j.status==='不支持'||verifiedEvidence(j).length));
 const unverifiedRequired=judgments.some(j=>['支持','部分支持','存在矛盾'].includes(j.status)&&!verifiedEvidence(j).length);
 if(combined==='部分支持'&&verifiedJudgment&&!unverifiedRequired){
  if(states.some(s=>s.color==='gray')||review.agent_result?.model_status==='incomplete')issues.push('部分判断未完成');
  return {color:'yellow',label:'部分支持',issues:[...new Set(issues)]};
 }
 if(!judgments.length||states.some(s=>s.color==='gray')||review.agent_result?.model_status==='incomplete')return {color:'gray',label:'未可靠完成',issues};
 if(combined==='支持')return {color:'green',label:'语义支持',issues:[]};
 if(combined==='部分支持')return {color:'yellow',label:'部分支持',issues};
 if(['不支持','存在矛盾'].includes(combined))return {color:'red',label:combined==='不支持'?'原文不支持':'存在矛盾',issues:[...new Set(states.flatMap(s=>s.issues))]};
 return {color:'gray',label:'证据不足',issues:[...new Set(states.flatMap(s=>s.issues))]};
}
function checkErrorFor(location){return (typeof task!=='undefined'&&task?.check_errors||[]).find(e=>e.startsWith((location?.id||'')+'：'))||''}
function sourceGrayDiagnostic(location,member,source){
 const match=member?.match||{},citation=[member?.author,member?.year].filter(Boolean).join(' '),status=match.status;
 if(status==='missing_attachment'||source?.attachment_status==='missing')return {label:'PDF 缺失',stage:'来源文件',reason:`${citation||'该引用'}没有可读取的来源 PDF。`,next:'上传对应来源 PDF 后重新匹配并补查。'};
 if(source?.attachment_status==='unreadable')return {label:'PDF 无法解析',stage:'PDF 解析',reason:`${source.filename||citation||'该来源'}已上传，但系统无法读取正文。`,next:'打开 PDF 检查密码或损坏情况，并替换为可读取文件。'};
 if(status==='needs_assignment')return {label:'来源存在歧义',stage:'来源身份',reason:match.reason||`${citation}存在多个候选来源，系统不能自动确认。`,next:'在“修正来源匹配”中人工选择正确 PDF，然后只补查该引用。'};
 if(status==='unmatched')return {label:'来源尚未匹配',stage:'来源身份',reason:match.reason||`${citation}尚未找到作者和年份均一致的来源。`,next:(match.candidates||[]).length?'核对候选 PDF 的作者、标题和年份后人工确认。':'上传对应 PDF，或核对已上传 PDF 的作者和年份。'};
 if(source?.metadata_verified===false)return {label:'书目信息未确认',stage:'来源身份',reason:`${source.filename||citation}的作者、标题或年份尚未确认。`,next:'核对 PDF 首页并确认书目信息后重新检查。'};
 return null;
}
function grayDiagnostic(location,review,member,source){
 const sourceProblem=member?sourceGrayDiagnostic(location,member,source):(location?.members||[]).map(m=>sourceGrayDiagnostic(location,m,typeof task!=='undefined'?task?.sources?.find(s=>s.id===m.match?.source_id):null)).find(Boolean);
 if(sourceProblem)return sourceProblem;
 if(review?.state==='stale')return {label:'来源已变化',stage:'结果失效',reason:'来源身份、书目信息或 PDF 已发生变化，旧核查结论不能继续沿用。',next:'对这一条执行补查；不需要重新检查未受影响的引用。'};
 const error=checkErrorFor(location);
 if(/Agent 判断引用了未提供的来源/.test(error))return {label:'模型引用了错误来源',stage:'模型结构化输出',reason:'模型返回了本轮没有提供的来源 ID，程序已拒绝保存该判断。',next:'重试该条；若重复出现，改用常规核查模式或缩小上下文。'};
 if(/共同判断无效/.test(error))return {label:'模型最终结论格式无效',stage:'模型结构化输出',reason:'模型返回了子判断，但最终综合结论缺失或不属于允许的标签，程序没有猜测转换。',next:'点击“重试未完成项”，只重新处理失败条目。'};
 if(/来源或判断状态无效/.test(error))return {label:'模型逐来源结果格式无效',stage:'模型结构化输出',reason:'模型返回的来源 ID、结论标签或字段结构不符合要求，结果被安全拒绝。',next:'点击“重试未完成项”；已成功条目不会重跑。'};
 if(/支持判断缺少证据/.test(error))return {label:'支持结论缺少证据',stage:'证据引用',reason:'模型声称支持，但没有提供可核验的原文证据 ID，系统不允许直接显示绿色。',next:'重试该条，或人工查看来源后确认。'};
 if(/摘录与真实原文|字符范围|唯一映射|片段ID|证据定位失败/.test(error))return {label:'原文证据验证失败',stage:'证据验证',reason:'模型引用的摘录无法在原始 PDF 文本中可靠验证；该语义判断已被阻止。',next:'查看 PDF 解析结果并补查；不要仅凭模型摘录下结论。'};
 if(/超时|连接|中断|退出/.test(error))return {label:'模型调用中断',stage:'模型调用',reason:error.replace(/^[^：]+：/,'')||'模型请求没有完整结束。',next:'确认模型连接后点击“重试未完成项”。'};
 const judgments=(review?.claims||[]).flatMap(c=>c.source_judgments||[]);
 if(review?.state==='complete'&&judgments.some(j=>['支持','部分支持','不支持','存在矛盾'].includes(j.status)&&!verifiedEvidence(j).length))return {label:'原文证据未验证',stage:'证据验证',reason:'已有语义判断，但必要证据没有通过原始 PDF 文本验证，所以不能显示绿、黄或红。',next:'检查 PDF 解析质量和证据摘录，再补查或人工复核。'};
 if(typeof window!=='undefined'&&window.isChecking)return {label:'正在核查',stage:'执行进度',reason:'该引用仍在队列中，尚未生成最终语义结果。',next:'等待当前检查完成。'};
 if(review?.state==='pending')return {label:'模型结果未保存',stage:'模型核查',reason:error?error.replace(/^[^：]+：/,''):'本轮没有生成符合要求的最终核查结果。',next:'点击“重试未完成项”，只处理灰色失败条目。'};
 if(review?.state==='partial')return {label:'核查材料不完整',stage:'材料或逐来源判断',reason:review.combined?.reason||'至少一个来源、阅读范围或逐来源判断不完整。',next:'展开逐来源详情，先解决列出的来源或证据问题。'};
 return {label:'尚未开始可靠核查',stage:'核查流程',reason:'当前没有可验证的语义判断和原文证据。',next:'开始检查或补查该引用。'};
}
function appendGrayDiagnostic(root,diagnostic){const box=el('div',undefined,'gray-diagnostic');box.append(el('strong',diagnostic.label),el('p','出错阶段：'+diagnostic.stage,'help'),el('p','具体原因：'+diagnostic.reason,'source-judgment'),el('p','下一步：'+diagnostic.next,'help'));root.append(box)}
// Original-source evidence, verified independently of semantic judgments.
function reviewSummaryStatus(review){
 if(!review||['pending','stale'].includes(review.state))return '待审查';
 return review.combined?.status||'待审查';
}
function reviewSummaryBadge(member,review){
 if(member.match?.year_diagnosis?.status==='confirmed_error')return {text:'引用年份错误',className:'badge problem'};
 if(member.match?.year_diagnosis?.status==='mismatch')return {text:'引用年份/PDF 不匹配',className:'badge problem'};
 if(member.match.status!=='matched')return {text:sourceGrayDiagnostic(null,member,null)?.label||labels[member.match.status],className:'badge neutral'};
 const judgments=(review?.claims||[]).flatMap(c=>c.source_judgments||[]).filter(j=>j.source_id===member.match.source_id),states=judgments.map(judgmentDisplayState);
 const colors=new Set(states.map(s=>s.color));
 const color=colors.has('yellow')||(colors.has('red')&&colors.has('green'))?'yellow':states.length&&states.every(s=>s.color==='red')?'red':states.length&&states.every(s=>s.color==='green')?'green':'gray';
 const text={red:'存在问题',yellow:'部分支持',green:'语义支持',gray:'未可靠完成'}[color];
 return {text,className:'badge result-'+color};
}
function downloadEvidence(kind){const a=el('a');a.href=`/api/tasks/${task.id}/evidence/${kind}`;a.download=kind==='prompt'?'codex-evidence-prompt.md':'evidence-package.json';a.click()}
function compactEvidence(judgments){
 const groups=new Map();
 for(const judgment of judgments)for(const e of judgment.evidence||[]){
  if(!['verified','text_verified'].includes(e.validation))continue;
  const page=e.regions?.[0]?.physical_page;
  // Never collapse different sources, roles, or known PDF occurrences.
  const key=JSON.stringify([e.source_id,e.pdf_sha256,e.role,page,e.block_id]);
  if(!groups.has(key))groups.set(key,[]);
  const group=groups.get(key),text=e.quote.normalize('NFKC').replace(/\s+/g,' ').trim();
  const claims=new Set([judgment.claim]);let candidate={...e,claims,text};
  for(let i=group.length-1;i>=0;i--){
   const old=group[i];
   if(!old.text.includes(text)&&!text.includes(old.text))continue;
   const located=e.location_state!=='unmapped'&&old.location_state!=='unmapped';
   if(located&&Number.isInteger(e.sentence_start)&&Number.isInteger(old.sentence_start)){
    const overlap=Math.min(e.sentence_end,old.sentence_end)-Math.max(e.sentence_start,old.sentence_start);
    if(overlap<=0)continue;
   }
   const sameClaims=[...old.claims].every(c=>claims.has(c));
   // A longer excerpt attached to another claim may contain necessary new facts.
   const chosen=sameClaims?(old.text.length<text.length?old:candidate):(old.text.length>text.length?old:candidate);
   candidate={...chosen,claims:new Set([...candidate.claims,...old.claims])};group.splice(i,1);
  }
  group.push(candidate);
 }
 const remaining=[...groups.values()].flat(),selected=[],covered=new Set();
 while(remaining.length&&selected.length<3){
  let best=0,score=-1;
  remaining.forEach((e,i)=>{const gain=[...e.claims].filter(c=>!covered.has(c)).length;if(gain>score){best=i;score=gain}});
  const [next]=remaining.splice(best,1);selected.push(next);for(const c of next.claims)covered.add(c);
 }
 return {evidence:selected,extra:remaining.length};
}
function sourceReviewEntries(review,sourceId){
 const judgments=(review?.claims||[]).flatMap(c=>c.source_judgments.filter(j=>j.source_id===sourceId).map(j=>({claim:c.text,...j})));
 return {judgments,...compactEvidence(judgments)};
}
function appendSourceReview(root,location,member,source,review){
 root.append(el('p','对应 PDF：'+(source?.filename||'未匹配到可读 PDF'),'source-file'));
 if(!source||member.match.status!=='matched'){appendGrayDiagnostic(root,grayDiagnostic(location,review,member,source));return}
 const entries=sourceReviewEntries(review,source.id);
 if(!review||review.state==='pending'||review.state==='stale'||!entries.judgments.length){appendGrayDiagnostic(root,grayDiagnostic(location,review,member,source));return}
 const sourceStates=entries.judgments.map(judgmentDisplayState),sourceColors=new Set(sourceStates.map(s=>s.color)),sourceColor=sourceColors.has('yellow')||(sourceColors.has('red')&&sourceColors.has('green'))?'yellow':sourceStates.length&&sourceStates.every(s=>s.color==='red')?'red':sourceStates.length&&sourceStates.every(s=>s.color==='green')?'green':'gray';
 root.append(el('strong',(review.model?.execution_mode==='agent'?'Agent ':'')+'逐来源结果：'+({red:'存在问题',yellow:'部分支持',green:'语义支持',gray:'未可靠完成'}[sourceColor]),'source-verdict result-'+sourceColor));
 for(const j of entries.judgments){const state=judgmentDisplayState(j),issues=state.issues.length?' · 问题类型：'+state.issues.join('、'):'';root.append(el('p','子观点：'+j.claim,'help'),el('p',j.status+' · '+j.reason+issues,'source-judgment'))}
 if(!entries.evidence.length)root.append(el('p','未取得可展示的已校验原文证据；不生成猜测高亮。','help'));
 for(const [i,e] of entries.evidence.entries()){const mapped=e.location_state==='mapped'&&e.regions?.length;const item=el('div',undefined,'evidence-item');item.append(el('span',`原文证据 ${i+1} · ${e.role} · 原文已验证 · ${mapped?'PDF 高亮可用（物理第 '+e.regions[0].physical_page+' 页）':'PDF 高亮不可用'}`,'pill'),el('blockquote',e.quote));if(mapped){const jump=el('button','查看来源 PDF 原文高亮 ↗');jump.onclick=()=>openEvidence(task,source,e);item.append(jump)}else{item.append(el('p','原文摘录已核实，语义结论保留；PDF 精确坐标不可用，请人工查看原文。','help'));const link=el('a','打开来源 PDF 人工查看 ↗');link.href='/api/assets/'+source.id+'/pdf';link.target='_blank';item.append(link)}if(e.claims?.size>1)item.append(el('p','对应子观点：'+[...e.claims].join('；'),'help'));root.append(item)}
 if(entries.extra)root.append(el('p',`本页最多展示三处去重后的证据；另有 ${entries.extra} 处已保存于完整报告。`,'help'));
}
function appendReviewConclusion(card,review,location){
 if(!review||review.state==='pending'||review.state==='stale'){const diagnostic=grayDiagnostic(location,review);const main=el('div',undefined,'display-verdict result-gray');main.append(el('strong',diagnostic.label),el('p','出错阶段：'+diagnostic.stage,'help'));card.append(main);appendGrayDiagnostic(card,diagnostic);card.append(el('p','综合结论：尚未形成可靠语义判断；这不表示原文支持或不支持。','combined'));return}
 const display=citationDisplayState(location||{members:[]},review),main=el('div',undefined,'display-verdict result-'+display.color);main.append(el('strong',display.label));if(display.issues.length)main.append(el('p','问题类型：'+display.issues.join('、'),'help'));card.append(main);
 if(review.coverage==='retrieved')card.append(el('p','检查范围：检索到的候选段落，未进行全文排除性核查。','help'));
 if(review.status_detail){const s=review.status_detail,words={confirmed:'来源已确认',unconfirmed:'来源未确认',retrieved:'已检索候选证据',full_text_reviewed:'已读取全文',verified:'原文已验证',partial:'部分原文已验证',failed:'原文验证失败',unverified:'原文未验证',mapped:'PDF 高亮可用',unmapped:'PDF 高亮不可用',none:'无可验证证据'};card.append(el('p',[words[s.source_identity_status],words[s.candidate_evidence_status],words[s.content_validation_status],words[s.localization_status],s.requires_human_review?'建议人工复核':'无需额外人工复核'].filter(Boolean).join(' · '),'help review-status-detail'))}
 card.append(el('p','综合结论：'+review.combined.status+' · '+review.combined.reason,'combined'));
 const basis=el('details',undefined,'decision-basis'),raw=review.combined?.model_original?.status||review.agent_result?.combined_status||review.combined.status,rule=review.combined?.label_adjustment||((review.combined?.model_original&&review.combined.model_original.status!==review.combined.status)?'来源、阅读范围或逐源判断完整性规则':null);basis.append(el('summary','查看判定依据'),el('p','Agent 原始语义判断：'+raw,'help'),el('p','程序保存的语义结论：'+review.combined.status,'help'),el('p','最终展示结论：'+display.label,'help'));if(rule)basis.append(el('p','程序规则调整：'+rule,'help'));if(review.combined?.technical_note)basis.append(el('p','技术处理：'+review.combined.technical_note,'help'));if(display.reason)basis.append(el('p','诊断：'+display.reason,'help'));card.append(basis);
 if(review.suggestion){const proposal=el('div',undefined,'suggestion');proposal.append(el('strong','修改建议'),el('p',review.suggestion.text));if(review.suggestion.verified){const b=el('button','采用建议');b.onclick=()=>applySuggestion(review,review.suggestion);proposal.append(b)}card.append(proposal)}
}
function renderEvidence(){const root=$('evidence-content');root.replaceChildren();if(!task){$('prepare-evidence').disabled=true;$('download-prompt').disabled=true;$('download-package').disabled=true;$('import-review').disabled=true;$('evidence-task').textContent='尚未创建检查任务';return}const pkg=task.evidence_package,review=task.evidence_review;$('prepare-evidence').disabled=false;$('evidence-task').textContent='任务 ID：'+task.id;$('download-prompt').disabled=!pkg;$('download-package').disabled=!pkg;$('import-review').disabled=!pkg;
 root.append(el('p','逐条结论、逐字原文证据与 PDF 高亮入口已显示在上方对应引用下。','help'));
 if(review)root.append(el('p',`核查模型：${review.model.name} · ${review.state==='complete'?'本轮核查完成':'仍有待复核或未完成项'}`,'help'));
 if(pkg){const detail=el('details');detail.append(el('summary','查看 PDF 材料读取范围'));for(const [sid,state] of Object.entries(pkg.source_states)){const source=task.sources.find(s=>s.id===sid);detail.append(el('p',`${source?.filename||source?.title||sid} · ${state.read_pages}/${state.total_pages} 页可读 · ${state.completeness==='complete'?'材料完整':state.completeness==='partial'?'材料部分可读':'材料不可读'}`,'help'))}root.append(detail)}
}
$('prepare-evidence').onclick=()=>work($('prepare-evidence'),async()=>{const id=task.id;await api(`/api/tasks/${id}/evidence/prepare`,{});task=await api('/api/tasks/'+id);report()});$('download-prompt').onclick=()=>downloadEvidence('prompt');$('download-package').onclick=()=>downloadEvidence('package');$('import-review').onclick=()=>$('review-file').click();$('review-file').onchange=e=>work($('import-review'),async()=>{let f=e.target.files[0];if(!f)return;if(f.size>20*1024*1024)throw Error('结果文件超过20MB');task=await api(`/api/tasks/${task.id}/evidence/import`,JSON.parse(await f.text()));report();e.target.value=''});$('refresh-review').onclick=()=>work($('refresh-review'),async()=>{task=await api('/api/tasks/'+task.id);report()});
