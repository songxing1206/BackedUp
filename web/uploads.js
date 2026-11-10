// PDF import feedback belongs to the source panel; no model requests.
function uploadConnectionError(error){return /failed to fetch|networkerror|load failed|fetch failed/i.test(error.message||'')}
function folderPdfFiles(files){const all=Array.from(files||[]),pdfs=all.filter(file=>/\.pdf$/i.test(file.name||''));return {pdfs,ignored:all.length-pdfs.length}}
async function uploadPdfs(files){
 if(!files.length||window.isUploading||window.isChecking)return;
 window.isUploading=true;let success=0,duplicate=0,failed=0,pending=0,disconnected=false;
 const feedback=$('upload-errors');feedback.replaceChildren();feedback.hidden=true;
 $('error').hidden=true;$('error').textContent='';
 for(const id of ['pdf-files','folder-files','new-check','run'])$(id).disabled=true;
 try{
  $('upload-status').textContent='正在连接本地服务…';
  const config=await api('/api/config');token=config.token;
  const known=new Set();for(const source of sources){const hash=await pdfHash(source);if(hash)known.add(hash)}
  for(let i=0;i<files.length;i++){
   const file=files[i];$('upload-status').textContent=`正在上传 ${i+1}/${files.length}：${file.name}`;
   try{
    if(file.size>15*1024*1024)throw Error('超过单个PDF的15 MB限制');
    const hash=await digest(await file.arrayBuffer());if(known.has(hash)){duplicate++;continue}
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('无法读取本地文件，请重新选择'));reader.readAsDataURL(file)});
    await merge([await api('/api/assets',{name:file.name,data})]);known.add(hash);success++;
   }catch(error){
    failed++;feedback.hidden=false;
    if(uploadConnectionError(error)){disconnected=true;pending=files.length-i-1;feedback.append(el('p',`${file.name}：上传连接中断，是否已保存尚未确认。恢复服务后重新选择文件，系统会按内容去重。`));break}
    feedback.append(el('p',`${file.name}：${error.message}`));
   }
  }
 }catch(error){
  pending=files.length;disconnected=uploadConnectionError(error);feedback.hidden=false;
  feedback.append(el('p',disconnected?'无法连接本地服务，本批文件尚未上传。请重新打开应用，恢复服务后再次选择文件。':'导入未开始：'+error.message));
 }finally{
  $('upload-status').textContent=`${disconnected?'上传已暂停':'上传结束'}：新增 ${success} 篇，跳过重复 ${duplicate} 篇，失败 ${failed} 篇${pending?'，尚未上传 '+pending+' 篇':''}`;
  window.isUploading=false;for(const id of ['pdf-files','folder-files','new-check','run'])$(id).disabled=!!window.isChecking;
 }
}
window.uploadPdfs=uploadPdfs;
$('folder-files').onchange=async event=>{const selected=folderPdfFiles(event.target.files);event.target.value='';if(!selected.pdfs.length){$('upload-status').textContent=`所选文件夹没有 PDF；已跳过 ${selected.ignored} 个非 PDF 文件`;return}await uploadPdfs(selected.pdfs);if(selected.ignored)$('upload-status').textContent+=`；跳过非 PDF ${selected.ignored} 个`};
