// Local data operations never call a model.
$('open-data').onclick=()=>work($('open-data'),async()=>{await api('/api/data/open',{})});
$('export-bundle').onclick=()=>work($('export-bundle'),async()=>{
 if(!task)return;
 await api(`/api/tasks/${task.id}/report-bundle/check`);
 const link=el('a');link.href=`/api/tasks/${task.id}/report-bundle`;link.download='backed-up-report.zip';link.click();
});
$('quit-service').onclick=async()=>{
 if(!confirm('退出本地服务？正在检查的任务将中断，已保存的报告保留。'))return;
 try{await api('/api/shutdown',{});$('error').hidden=false;$('error').textContent='本地服务已退出。重新打开应用或启动.command 即可继续使用。'}
 catch{$('error').hidden=false;$('error').textContent='无法连接本地服务，请在启动入口检查状态。'}
};

$('licenses-open').onclick=async()=>{
 const dialog=$('licenses-dialog'),content=$('licenses-content');content.replaceChildren(el('p','正在加载许可信息…','help'));dialog.showModal();
 try{
  const data=await api('/api/licenses');content.replaceChildren();
  content.append(el('h3','复用与适配说明'),el('p','CiteFact：复用 APA 引用解析器及基础审查提示词；Backed Up 增加了中文与位置适配、逐源核查、检索、原文校验和 PDF 高亮等功能。其余依赖用于 PDF 解析与渲染、本地存储、网络与打包运行。'));
  for(const item of data.documents){const details=el('details'),summary=el('summary',item.name),text=el('pre',item.text);details.append(summary,text);content.append(details)}
 }catch(error){content.replaceChildren(el('p','许可信息加载失败：'+error.message,'help'))}
};
$('licenses-close').onclick=()=>$('licenses-dialog').close();
