"""Portable, script-free reports with PDFs and saved-coordinate highlights."""
import html,io,json,re,tempfile,zipfile,hashlib,os
from pathlib import Path
from PIL import Image,ImageDraw
from .pdf_index import fingerprint,render_page

def esc(value):return html.escape(str(value or ''),quote=True)

def source_path(source,root):
 path=Path(source.get('path') or '').resolve()
 try:path.relative_to((Path(root)/'assets').resolve())
 except ValueError:raise ValueError('参考文献不在该历史数据目录，未导出') from None
 if not path.is_file():raise ValueError('参考文献文件缺失，无法生成完整报告包')
 return path

def highlighted_page(path,regions):
 page=regions[0]['page_index'];image=Image.open(io.BytesIO(render_page(path,page,1.25))).convert('RGBA')
 overlay=Image.new('RGBA',image.size);draw=ImageDraw.Draw(overlay)
 for r in regions:
  if r['page_index']!=page:continue
  x,y,w,h=r['box'];sx=image.width/r['page_width'];sy=image.height/r['page_height']
  draw.rectangle((x*sx,y*sy,(x+w)*sx,(y+h)*sy),fill=(125,90,190,65),outline=(100,65,160,220),width=2)
 output=io.BytesIO();Image.alpha_composite(image,overlay).convert('RGB').save(output,format='PNG');return output.getvalue()

def write_report(task,root,destination):
 if task.get('schema_version')!=1:raise ValueError('不支持该历史报告格式；请使用之前导出的独立报告包')
 sources={s['id']:s for s in task.get('sources',[])};paths={};hashes={};sections=[]
 with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
  for sid,source in sources.items():
   if not re.fullmatch('[a-f0-9]{32}',sid):raise ValueError('来源编号无效')
   if not source.get('path'):continue
   path=source_path(source,root);paths[sid]=path;hashes[sid]=fingerprint(path)
   if source.get('sha256') and hashes[sid]!=source['sha256']:raise ValueError('参考文献 PDF 已变化，不能导出旧证据高亮')
   archive.write(path,f'sources/{sid}.pdf')
  reviews={r['location_id']:r for r in task.get('evidence_review',{}).get('locations',[])}
  for location in task.get('locations',[]):
   row=reviews.get(location['id'],{});combined=row.get('combined',{});body=[]
   if row.get('state') in {'stale','pending'}:combined={'status':'尚未完成','reason':'旧检查结果已失效或尚未核查；下方历史判断仅供复核。'}
   for claim in row.get('claims',[]):
    body.append('<h3>'+esc(claim.get('text'))+'</h3>')
    for judgment in claim.get('source_judgments',[]):
     sid=judgment['source_id'];source=sources.get(sid,{})
     body.append('<p><strong>'+esc(source.get('filename') or source.get('title') or sid)+'</strong> · '+esc(judgment.get('status'))+'</p><p>'+esc(judgment.get('reason'))+'</p>')
     if sid in paths:body.append(f'<p><a href="sources/{sid}.pdf">打开完整参考文献 PDF</a></p>')
     for evidence in judgment.get('evidence',[]):
      body.append('<blockquote>'+esc(evidence.get('quote'))+'</blockquote>')
      if row.get('state')=='stale' or evidence.get('validation')!='verified' or not evidence.get('regions'):
       body.append('<p>本条证据未提供可验证的位置高亮。</p>');continue
      if sid not in paths or evidence.get('pdf_sha256')!=hashes[sid]:raise ValueError('参考文献 PDF 与已保存证据指纹不一致，未导出高亮')
      eid=evidence['id']
      if not re.fullmatch('[a-f0-9]{32}',eid):raise ValueError('证据编号无效')
      for page in sorted({r['page_index'] for r in evidence['regions']}):
       regions=[r for r in evidence['regions'] if r['page_index']==page];name=f'evidence/{eid}-{page}.png'
       archive.writestr(name,highlighted_page(paths[sid],regions))
       body.append(f'<details><summary>查看保存的高亮 · 物理第 {page+1} 页</summary><a href="{name}"><img src="{name}" alt="已保存证据高亮"></a></details>')
   if row.get('coverage')=='retrieved':body.insert(0,'<p>检查范围：检索到的候选段落，未进行全文排除性核查。</p>')
   sections.append('<article id="'+esc(location['id'])+'"><h2>'+esc(location['id'])+'</h2><p>'+esc(location.get('claim_text') or location.get('sentence'))+'</p><p class="verdict">综合结论：'+esc(combined.get('status') or '尚未完成')+' · '+esc(combined.get('reason'))+'</p>'+''.join(body)+'</article>')
  evaluation=task.get('evaluation',{});counts=evaluation.get('counts',{})
  context={'bm25':'BM25','bm25_neighbor':'BM25 + 邻近上下文','deep':'深度核查'}.get(evaluation.get('context_mode'),'未记录')
  duration=evaluation.get('duration_seconds')
  duration_label=(str(round(duration,2))+' 秒（从任务创建计时，含等待/暂停）') if isinstance(duration,(int,float)) and duration>=0 else '未记录'
  quality=('<section><h2>本轮结果质量检查</h2><p>执行模式：'+esc(evaluation.get('execution_mode','旧版'))+' · 上下文：'+esc(context)+' · 完成 '+esc(counts.get('completed',0))+'/'+esc(counts.get('required',0))+' · 来源待确认 '+esc(counts.get('source_unconfirmed',0))+' · 需人工复核 '+esc(counts.get('human_review',0))+'</p><p>模型请求 '+esc(evaluation.get('model_requests',0))+' 次 · 实际 Token '+esc(evaluation.get('total_tokens') if evaluation.get('total_tokens') is not None else '未返回')+' · 本轮耗时 '+esc(duration_label)+'</p><p>此摘要不代表语义准确率。</p></section>') if evaluation else ''
  markup='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Backed Up 历史报告</title><style>body{font:17px/1.7 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#292335}article{border:1px solid #ddd;padding:24px;margin:24px 0}blockquote,.verdict{background:#f3effa;padding:16px}img{max-width:100%}p,blockquote{white-space:pre-wrap}a{color:#65528e}</style><h1>Backed Up 引用检查报告</h1><p>只读归档；展示保存的结论与证据，不重新调用模型。高亮图为保存坐标渲染的证据页，完整 PDF 用于阅读上下文。</p>'''+ '<p>任务创建时间：'+esc(task.get('created_at'))+' · 核查模型：'+esc(task.get('evidence_review',{}).get('model',{}).get('name'))+'</p>'+quality+'<details><summary>保存的正文</summary><p>'+esc(task.get('text'))+'</p></details>'+''.join(sections)+'</html>'
  archive.writestr('report.html',markup)
  archive.writestr('README.txt','解压整个报告包，打开 report.html。请保留 sources 和 evidence 文件夹。报告含论文内容和参考文献，分享前请确认。无需启动产品或连接模型。')
  # Guard against a PDF changing between validation, copying and rendering.
  if any(fingerprint(paths[sid])!=digest for sid,digest in hashes.items()):raise ValueError('导出期间 PDF 发生变化，请重试')

def report_bundle(task,root):
 file=tempfile.TemporaryFile()
 try:write_report(task,root,file);file.seek(0);return file
 except Exception:file.close();raise

def saved_bundle(task,root,cache):
 """Reuse rendered archives while task and source files remain unchanged."""
 files=[]
 for source in task.get('sources',[]):
  if source.get('path'):
   path=source_path(source,root);stat=path.stat();files.append([str(path),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns])
 key=hashlib.sha256(json.dumps([task,files,'archive-2'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 directory=Path(cache);directory.mkdir(parents=True,exist_ok=True);target=directory/(key+'.zip')
 if not target.exists():
  fd,name=tempfile.mkstemp(dir=directory,suffix='.tmp');os.close(fd);temporary=Path(name)
  try:write_report(task,root,temporary);temporary.replace(target)
  finally:temporary.unlink(missing_ok=True)
 return target.open('rb')
