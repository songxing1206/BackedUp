import json,unittest,threading
from unittest.mock import patch
import test_automatic_review as fixtures
from app.response_recovery import complete_claims,review_response,ResponseError
from app.model_provider import ModelClient
from app.automatic_review import ReviewQueue

class RecoveryParserTests(unittest.TestCase):
 def test_only_complete_top_level_claims_are_recovered(self):
  raw='{"claims":[{"id":"P1","text":"quoted } bracket","source_judgments":[]},{"id":"P2"'
  self.assertEqual([c['id'] for c in complete_claims(raw)],['P1'])
  self.assertEqual(complete_claims('{"text":"fake \\"claims\\": ["'),[])
 def test_complete_judgment_inside_unclosed_claim_is_recovered(self):
  raw='{"claims":[{"id":"P1","text":"claim","source_judgments":[{"source_id":"one","status":"支持"},{"source_id":"two"'
  claims=complete_claims(raw)
  self.assertEqual(claims[0]['source_judgments'],[{'source_id':'one','status':'支持'}])
 def test_finished_json_is_unchanged_but_length_is_partial(self):
  text='{"claims":[{"id":"P1"}],"combined":{"status":"支持"}}'
  self.assertNotIn('_response_incomplete',review_response(text,'stop'))
  self.assertTrue(review_response(text,'length')['_response_incomplete'])
 def test_provider_preserves_raw_diagnostic_without_resending(self):
  c=ModelClient(dict(provider='deepseek',model='deepseek-flash',api_key='test',_output_limit=6000,_purpose='review'))
  with patch.object(c,'_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{"claims":['}}]}) as request:
   with self.assertRaises(ResponseError):c.call('JSON')
   self.assertEqual(request.call_count,1);self.assertEqual(c.last_response['finish_reason'],'length');self.assertEqual(c.last_response['raw'],'{"claims":[')

class ReviewPartialTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def test_failed_repair_retains_verified_claim_and_durable_response(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  task=self.tasks.create('Training improved recall (Smith, 2023).',[self.s]);pkg=self.evidence.prepare(task['id']);sid=self.s['id'];index=pkg['sources'][sid];block=index['pages'][0]['blocks'][-1]
  claim=dict(id='P1',text='Training improved recall',source_judgments=[dict(source_id=sid,status='支持',reason='evidence',evidence=[dict(source_id=sid,pdf_sha256=index['sha256'],block_id=block['id'],quote=block['text'],role='支持')])])
  calls=[]
  class Fake:
   def call(_,prompt,event):
    calls.append(json.loads(prompt.split('\nDATA\n')[1]))
    if len(calls)==1:return dict(claims=[claim],_response_incomplete=True)
    raise ResponseError('模型返回非完整 JSON')
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda _:Fake());jid='e'*32;q.events[jid]=threading.Event()
  try:
   data=dict(phase='review',location_id='C001',sentence=task['text'],sources=[])
   row=q._validated_call(jid,Fake(),'JSON',data,pkg,{sid})
   self.assertEqual(len(calls),2);self.assertEqual(row['claims'][0]['source_judgments'][0]['status'],'支持');self.assertEqual(row['combined']['status'],'无法判断')
   self.assertTrue(row['response_incomplete']);self.assertTrue(list((self.root/'checkpoints').glob('*partial*')))
   self.assertTrue(any(json.loads(p.read_text(encoding='utf-8')).get('state')=='response_invalid' for p in (self.root/'checkpoints').glob('*.json')))
  finally:q.close()
