import json,threading,unittest
from unittest.mock import patch
import test_automatic_review as fixtures
from app.automatic_review import ReviewQueue,CheckpointBlocked
from app.model_provider import ModelClient,ModelConnectionError

class ExplicitRetryTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def queue(self,client):return ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda _:client)
 def test_network_failure_pauses_then_explicit_retry_recovers(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'));calls=[]
  class Fake:
   def call(_,prompt,event):
    d=json.loads(prompt.split('\nDATA\n')[1]);calls.append(d)
    if len(calls)==1:raise ModelConnectionError('无法连接模型服务或请求超时')
    s=d['sources'][0];b=next(b for b in s['blocks'] if 'Training' in b['text'])
    return dict(claims=[dict(id='P1',text='Training improved recall',source_judgments=[dict(source_id=s['id'],status='支持',reason='verified',evidence=[dict(source_id=s['id'],pdf_sha256=s['sha256'],block_id=b['id'],quote=b['text'],role='支持')])])],combined=dict(status='支持',reason='verified'))
  q=self.queue(Fake())
  try:
   first=q.start('Training improved recall (Smith, 2023). Training improved recall among adults (Smith, 2023).',[self.s['id']]);q.wait(first['id'])
   self.assertEqual(q.get(first['id'])['status'],'paused');self.assertEqual(len(calls),1);self.assertEqual(q.get(first['id'])['completed'],0)
   second=q.retry(first['id']);q.wait(second['id']);self.assertTrue(q.get(second['id'])['retry_failed_requests']);self.assertEqual(q.get(second['id'])['status'],'completed');self.assertEqual(len(calls),3)
  finally:q.close()
 def test_unknown_request_is_still_blocked_on_explicit_retry(self):
  class Fake:
   def call(_,p,e):raise ModelConnectionError('timeout')
  q=self.queue(Fake());jid='c'*32;q.events[jid]=threading.Event()
  try:
   with self.assertRaises(ModelConnectionError):q._call(jid,Fake(),'JSON',dict(phase='review'))
   p=next((self.root/'checkpoints').glob('*.json'));d=json.loads(p.read_text());d['state']='requested';p.write_text(json.dumps(d))
   new='d'*32;q.events[new]=threading.Event();q._save(dict(id=new,status='paused',model={},retry_failed_requests=True,token_budget=500000,max_requests=60))
   with self.assertRaises(CheckpointBlocked):q._call(new,Fake(),'JSON',dict(phase='review'))
  finally:q.close()
 def test_transport_diagnostics_have_failure_event(self):
  client=ModelClient(dict(provider='custom',model='test',api_key='not-a-real-key',base_url='https://example.invalid/v1',_output_limit=6000))
  with patch('urllib.request.build_opener') as opener,patch.object(client,'_audit') as audit:
   opener.return_value.open.side_effect=TimeoutError()
   with self.assertRaises(ModelConnectionError):client.call('JSON')
   self.assertEqual(opener.return_value.open.call_count,1);self.assertEqual([c.args[2] for c in audit.call_args_list],['started','failed']);self.assertEqual(audit.call_args.kwargs['error_kind'],'TimeoutError')
