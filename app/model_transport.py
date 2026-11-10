"""Bounded OpenAI SSE reader and separate connect/response timeouts."""
import http.client,json,time,urllib.request

CONNECT_TIMEOUT=30
RESPONSE_TIMEOUT=600
MAX_RESPONSE=16*1024*1024

class ReviewHTTPSHandler(urllib.request.HTTPSHandler):
 def __init__(self,progress,response_timeout=RESPONSE_TIMEOUT):
  super().__init__();self.progress=progress;self.response_timeout=response_timeout
 def https_open(self,request):
  progress=self.progress;response_timeout=self.response_timeout
  class Connection(http.client.HTTPSConnection):
   def connect(self):
    self.timeout=CONNECT_TIMEOUT
    super().connect()
    self.sock.settimeout(response_timeout)
    progress['phase']='waiting_headers'
  options={'context':self._context}
  if hasattr(self,'_check_hostname'):options['check_hostname']=self._check_hostname
  return self.do_open(Connection,request,**options)

def read_completion(response,cancel,started,progress,on_output=None,timeout_seconds=RESPONSE_TIMEOUT,on_phase=None,on_activity=None):
 """Accept SSE or a gateway's JSON fallback; never return an unfinished stream."""
 def check_deadline():
  if cancel.is_set():raise ValueError('任务已取消')
  remaining=timeout_seconds-(time.monotonic()-started)
  if remaining<=0:raise TimeoutError('模型响应超过等待上限')
  sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
  if sock is not None:sock.settimeout(remaining)
 if 'text/event-stream' not in response.headers.get('Content-Type','').lower():
  chunks=[];size=0
  while True:
   check_deadline();chunk=response.read1(min(65536,MAX_RESPONSE-size+1))
   if not chunk:break
   progress.setdefault('first_byte_seconds',round(time.monotonic()-started,2))
   size+=len(chunk)
   if size>MAX_RESPONSE:raise ValueError('模型响应过大')
   chunks.append(chunk)
  return json.loads(b''.join(chunks))
 content=[];finish=None;usage={};size=0;done=False;event=[];last_activity=started;phases=set()
 def consume(lines):
  nonlocal finish,usage,done
  data='\n'.join(line[5:].lstrip(' ') for line in lines if line.startswith('data:'))
  if not data:return
  if data.strip()=='[DONE]':done=True;return
  row=json.loads(data)
  if row.get('error'):raise ValueError('模型流式响应返回错误，检查未完成')
  if row.get('usage'):usage.update(row['usage']);progress['usage']=dict(usage)
  for choice in row.get('choices',[]):
   if choice.get('index',0)!=0:continue
   delta=choice.get('delta',{})
   for field,phase in [('reasoning_content','reasoning'),('content','answer')]:
    if delta.get(field):
     progress[phase+'_chars']=progress.get(phase+'_chars',0)+len(delta[field])
     if phase not in phases:
      phases.add(phase);progress[phase+'_started_seconds']=round(time.monotonic()-started,2)
      if on_phase:on_phase(phase)
   if (delta.get('content') or delta.get('reasoning_content')) and 'model_output_seconds' not in progress:
    progress['model_output_seconds']=round(time.monotonic()-started,2)
    if on_output:on_output(progress['model_output_seconds'])
   # reasoning_content belongs to inference, never to the answer JSON.
   if delta.get('content'):content.append(delta['content'])
   if choice.get('finish_reason') is not None:finish=choice['finish_reason']
  progress['events']=progress.get('events',0)+1
 while not done:
  check_deadline()
  line=response.readline(min(MAX_RESPONSE-size+1,1024*1024))
  if not line:break
  size+=len(line)
  if size>MAX_RESPONSE:raise ValueError('模型响应过大')
  progress.setdefault('first_byte_seconds',round(time.monotonic()-started,2))
  line=line.decode('utf-8').rstrip('\r\n')
  if not line:
   consume(event);event=[]
  elif not line.startswith(':'):event.append(line)
  if on_activity and time.monotonic()-last_activity>=60:
   last_activity=time.monotonic();on_activity()
 if event and not done:consume(event)
 if not done:raise http.client.RemoteDisconnected('模型数据流提前结束')
 return {'choices':[{'message':{'content':''.join(content)},'finish_reason':finish}],'usage':usage}
