"""Exercise the frozen app in temporary data directories, with fixture verdicts."""
import base64,io,json,os,subprocess,sys,tempfile,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from app.runtime import instance_id
from pdf_fixture import make_pdf

def main():
 executable=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'dist/BackedUp.app/Contents/MacOS/BackedUp'
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with tempfile.TemporaryDirectory(prefix='backed-up-package-') as d:
  root=Path(d);environment={**os.environ,'BACKEDUP_DATA_HOME':str(root/'data'),'BACKEDUP_CACHE_HOME':str(root/'cache'),'HTTPS_PROXY':'http://127.0.0.1:1','HTTP_PROXY':'http://127.0.0.1:1','NO_PROXY':'localhost,127.0.0.1'}
  process=subprocess.Popen([str(executable),'--no-browser'],env=environment)
  base=None;token=''
  def request(route,body=None):
   data=json.dumps(body).encode() if body is not None else None
   req=urllib.request.Request(base+route,data=data,headers={'Content-Type':'application/json','X-BackedUp-Token':token})
   with opener.open(req,timeout=20) as response:return response.read()
  try:
   deadline=time.monotonic()+20
   while time.monotonic()<deadline:
    for port in range(8787,8798):
     try:
      with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=.2) as response:state=json.loads(response.read())
      if state.get('instance')==instance_id(root/'data/data-v1'):base=f'http://localhost:{port}';break
     except (OSError,ValueError):pass
    if base:break
    if process.poll() is not None:raise RuntimeError('冻结应用提前退出')
    time.sleep(.1)
   if not base:raise RuntimeError('冻结应用未就绪')
   token=json.loads(request('/api/config'))['token']
   licenses=json.loads(request('/api/licenses'));assert any('José Fernandes' in x['text'] and 'Permission is hereby granted' in x['text'] for x in licenses['documents'])
   html=request('/')
   assert b'licenses-open' in html
   assert b'local-data.js' in html
   assert 'API 服务地址（Base URL）'.encode() in html
   assert '高级：服务地址'.encode() not in html
   assert b'export-bundle' in request('/local-data.js')
   progress=request('/automatic-review.js')
   assert b'function userCheckStage' in progress and b'check-issue' not in progress
   pdf=make_pdf(root/'fixture.pdf',pages=[[(50,730,'Smith 2023 Attention Study'),(50,710,'Training improved recall in adults.')]])
   source=json.loads(request('/api/assets',{'name':'Smith.pdf','data':base64.b64encode(pdf.read_bytes()).decode()}))
   source=json.loads(request(f'/api/assets/{source["id"]}/confirm',{'title':'Attention Study','authors':'Smith','year':'2023'}))
   preflight=json.loads(request('/api/checks/preflight',{'text':'Training improved recall (Smith, 2023).','source_ids':[source['id']]}))
   assert preflight['model_calls']==0 and preflight['readable_files']==1
   task=json.loads(request('/api/tasks',{'text':'Training improved recall (Smith, 2023).','source_ids':[source['id']]}))
   package=json.loads(request(f'/api/tasks/{task["id"]}/evidence/prepare',{}));sid=source['id'];index=package['sources'][sid];block=index['pages'][0]['blocks'][1]
   verdict={'task_id':task['id'],'package_id':package['package_id'],'model':{'name':'offline fixture'},'reading':{sid:[1]},'locations':[{'location_id':task['locations'][0]['id'],'claims':[{'id':'P1','text':'Training improved recall','source_judgments':[{'source_id':sid,'status':'支持','reason':'offline fixture','evidence':[{'source_id':sid,'pdf_sha256':index['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'offline fixture'}}]}
   request(f'/api/tasks/{task["id"]}/evidence/import',verdict)
   bundle=request(f'/api/tasks/{task["id"]}/report-bundle')
   with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
    assert any(name.endswith('.png') for name in archive.namelist());assert any(name.endswith('.pdf') for name in archive.namelist());assert b'127.0.0.1' not in archive.read('report.html')
    archive.extractall(root/'moved-report')
   assert len(json.loads(request('/api/history')))==1
   request('/api/model/settings',{'provider':'openai','model':'offline-fixture','api_key':'not-a-real-key','session_only':True})
   job=json.loads(request('/api/checks',{'text':'Quantum mechanics (Smith, 2023).','source_ids':[sid],'location_limit':3,'review_mode':'retrieval'}))
   for _ in range(100):
    state=json.loads(request('/api/checks/'+job['id']))
    if state['status'] not in {'running','queued'}:break
    time.sleep(.05)
   assert state['status']=='partial',state
   assert state.get('budget_usage',{}).get('requests',0)==0
   assert list((root/'cache').rglob('*.sqlite'))
   audit=root/'data/data-v1/logs/api-requests.jsonl'
   assert not audit.exists() or not audit.read_text().strip()
   assert b'sources/' in request(f'/api/history/data-v1/{task["id"]}/report')
   reuse=subprocess.run([str(executable),'--no-browser'],env=environment,timeout=10);assert reuse.returncode==0
   deleted=request(f'/api/history/data-v1/{task["id"]}/delete',{})
   assert json.loads(deleted)['ok']
   assert all(row['id']!=task['id'] for row in json.loads(request('/api/history')))
   assert not (root/'data/data-v1/tasks'/f'{task["id"]}.json').exists()
   assert (root/'data/data-v1/tasks'/f'{task["id"]}.deleted').exists()
   request('/api/shutdown',{});process.wait(timeout=10);assert process.returncode==0
   print('冻结 macOS 应用通过：启动、PDF上传/解析、高亮归档ZIP、只读历史、重复启动、退出。无真实模型调用。')
  finally:
   if process.poll() is None:process.terminate();process.wait(timeout=10)

if __name__=='__main__':main()
