import json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import test_automatic_review as fixtures
from app.model_settings import SettingsStore
from app.model_provider import ModelClient,ModelOutputLimitError
from app.reasoning_policy import request_profile
from app.automatic_review import ReviewQueue
from app.model_transport import read_completion
from test_model_transport import Response,event

class ReasoningPolicyTests(unittest.TestCase):
 def settings(self):return dict(provider='custom',model='deepseek-reasoner',base_url='https://models.sjtu.edu.cn/api/v1',api_key='fixture')
 def test_keeps_reasoner_and_thinking_with_separate_output_allowance(self):
  client=ModelClient({**self.settings(),'_output_limit':6000,'_purpose':'review'})
  with patch.object(client,'_request',return_value={'choices':[{'message':{'content':'{"claims":[]}'},'finish_reason':'stop'}]}) as call:
   client.call('JSON');payload=call.call_args.args[1]
   self.assertEqual(payload['model'],'deepseek-reasoner');self.assertEqual(payload['thinking'],{'type':'enabled'})
   self.assertEqual(payload['reasoning_effort'],'high');self.assertEqual(payload['max_tokens'],32768)
 def test_configurable_profile_validates_before_saving(self):
  with tempfile.TemporaryDirectory() as directory:
   store=SettingsStore(Path(directory)/'settings.json')
   fields={**self.settings(),'reasoning_effort':'low','reasoning_output_tokens':65536,'reasoning_timeout_seconds':3600}
   public=store.save(fields);self.assertEqual(public['reasoning_output_tokens'],65536);self.assertNotIn('api_key',public)
   for field,value in [('reasoning_output_tokens',True),('reasoning_output_tokens',999999),('reasoning_effort','none'),('reasoning_timeout_seconds',0)]:
    with self.assertRaises(ValueError):store.save({**fields,field:value})
 def test_ordinary_mode_has_no_thinking_profile(self):
  self.assertIsNone(request_profile({**self.settings(),'model':'deepseek-chat'}))
 def test_output_exhaustion_is_budget_failure_not_json_repair(self):
  client=ModelClient({**self.settings(),'_output_limit':32768,'_purpose':'review'})
  with patch.object(client,'_request',return_value={'choices':[{'message':{'content':''},'finish_reason':'length'}]}) as call:
   with self.assertRaises(ModelOutputLimitError):client.call('JSON')
   self.assertEqual(call.call_count,1);self.assertEqual(client.last_response['finish_reason'],'length')
 def test_stream_can_finish_after_old_600_second_limit(self):
  body=event({'choices':[{'delta':{'reasoning_content':'thinking'}}]})+event({'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':'stop'}]})+b'data: [DONE]\n\n'
  progress={};phases=[]
  row=read_completion(Response(body),threading.Event(),time.monotonic()-901,progress,timeout_seconds=1800,on_phase=phases.append)
  self.assertEqual(json.loads(row['choices'][0]['message']['content']),{'ok':True})
  self.assertEqual(phases,['reasoning','answer']);self.assertEqual(progress['reasoning_chars'],8);self.assertGreater(progress['answer_chars'],0)

class ReasoningQueueTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def test_exhaustion_pauses_once_and_same_profile_reuses_saved_failure(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  settings=dict(provider='custom',model='deepseek-reasoner',api_key='fixture',base_url='https://models.sjtu.edu.cn/api/v1')
  client=ModelClient(settings)
  def response(*args):
   client.last_usage={'total_tokens':1234}
   return {'choices':[{'message':{'content':''},'finish_reason':'length'}]}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:settings,lambda _:client)
  try:
   with patch.object(client,'_request',side_effect=response) as call:
    job=q.start('Training improved recall (Smith, 2023).',[self.s['id']],max_requests=1,token_budget=80000);q.wait(job['id'])
    result=q.get(job['id']);self.assertEqual(result['status'],'paused');self.assertEqual(result['stage'],'单次输出达到上限，结果已保存');self.assertEqual(call.call_count,1)
    self.assertEqual(result['model']['request_profile']['output_tokens'],32768);self.assertEqual(result['budget_usage']['actual_tokens'],1234)
    self.assertTrue(any(json.loads(p.read_text(encoding='utf-8'))['state']=='output_limited' for p in (self.root/'checkpoints').glob('*.json')))
    retry=q.retry(job['id']);q.wait(retry['id']);self.assertEqual(call.call_count,1)
    settings['reasoning_output_tokens']=65536
    changed=q.start('Training improved recall (Smith, 2023).',[self.s['id']],job.get('task_id'),max_requests=1,token_budget=100000,retry_failed_requests=True);q.wait(changed['id']);self.assertEqual(call.call_count,2)
  finally:q.close()
