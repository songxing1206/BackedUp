import unittest,tempfile,threading,json,os
from pathlib import Path
from unittest.mock import patch
from app.model_settings import SettingsStore
from app.model_provider import ModelClient,parse_json

class ModelTests(unittest.TestCase):
 def test_new_install_prefills_chat_endpoint_without_a_secret(self):
  with tempfile.TemporaryDirectory() as d:
   public=SettingsStore(Path(d)/'model.json').public()
   self.assertEqual((public['provider'],public['model'],public['base_url']),('custom','deepseek-chat','https://models.sjtu.edu.cn/api/v1'))
   self.assertFalse(public['has_key'])
 def test_secret_permissions_snapshot_and_clear(self):
  with tempfile.TemporaryDirectory() as d:
   s=SettingsStore(Path(d)/'model.json');s.save({'provider':'deepseek','model':'test','api_key':'secret123','session_only':False})
   if os.name!='nt':self.assertEqual(os.stat(s.path).st_mode&0o777,0o600)
   self.assertNotIn('secret123',json.dumps(s.public()))
   snap=s.snapshot();s.save({'provider':'deepseek','model':'other','api_key':''})
   self.assertEqual(s.snapshot()['api_key'],'secret123');self.assertEqual(snap['model'],'test')
   s.save({'provider':'deepseek','model':'test','clear_key':True});self.assertFalse(s.public()['has_key'])
 def test_session_only(self):
  with tempfile.TemporaryDirectory() as d:
   s=SettingsStore(Path(d)/'m');s.save({'provider':'deepseek','model':'test','api_key':'secret','session_only':True})
   self.assertFalse(s.path.exists());self.assertTrue(s.public()['has_key'])
 def test_reject_unsafe_endpoint(self):
  with tempfile.TemporaryDirectory() as d:
   s=SettingsStore(Path(d)/'m')
   for url in ['http://evil.com/v1','https://user:pass@evil.com/v1','file:///tmp/test','https://evil.com/v1?key=test']:
    with self.assertRaises(ValueError):s.save({'provider':'custom','base_url':url,'model':'test','api_key':'key'})
 def test_json_and_cancel(self):
  self.assertEqual(parse_json('```json\n{"ok":true}\n```'),{'ok':True})
  with self.assertRaises(ValueError):parse_json('not json')
  event=threading.Event();event.set()
  with self.assertRaises(ValueError):ModelClient({'provider':'deepseek','model':'x','api_key':'y'}).call('test',event)
 def test_protocol_and_minimal_test(self):
  c=ModelClient({'provider':'deepseek','model':'x','api_key':'s','base_url':'https://api.deepseek.com'})
  with patch.object(c,'_request',return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}) as request:
   self.assertEqual(c.test()['ok'],True)
   payload=request.call_args.args[1];self.assertNotIn('论文',json.dumps(payload));self.assertEqual(payload['model'],'x')

class ProtocolTests(unittest.TestCase):
 def test_anthropic_response_and_headers(self):
  c=ModelClient({'provider':'anthropic','model':'x','api_key':'secret','base_url':'https://api.anthropic.com/v1'})
  with patch.object(c,'_request',return_value={'content':[{'type':'text','text':'{"answer":1}'}]}) as request:
   self.assertEqual(c.call('test'),{'answer':1});self.assertEqual(request.call_args.args[0],'https://api.anthropic.com/v1/messages');self.assertEqual(request.call_args.args[2]['x-api-key'],'secret')
 def test_truncated_response_rejected(self):
  c=ModelClient({'provider':'openai','model':'x','api_key':'secret','base_url':'https://api.openai.com/v1'})
  with patch.object(c,'_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}):
   with self.assertRaisesRegex(ValueError,'截断'):c.call('test')
 def test_unreadable_json_response(self):
  c=ModelClient({'provider':'deepseek','model':'x','api_key':'secret'})
  with patch.object(c,'_request',return_value={'choices':[]}):
   with self.assertRaisesRegex(ValueError,'格式'):c.call('test')

class JsonModeRegression(unittest.TestCase):
 def test_json_mode_always_has_json_instruction(self):
  for provider in ['deepseek','custom']:
   c=ModelClient({'provider':provider,'model':'x','api_key':'secret','base_url':'https://api.deepseek.com'})
   with patch.object(c,'_request',return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}) as request:
    c.test();payload=request.call_args.args[1]
    self.assertTrue(any('json' in m['content'].lower() for m in payload['messages']))

class DeepSeekReliabilityTests(unittest.TestCase):
 def client(self):return ModelClient({'provider':'deepseek','model':'deepseek-flash','api_key':'test'})
 def test_explicit_bounded_thinking(self):
  c=self.client()
  with patch.object(c,'_request',return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}) as request:
   c.call('Return JSON evidence')
   self.assertEqual(request.call_args.args[1]['reasoning_effort'],'low')
 def test_one_retry_for_truncated_or_invalid_json(self):
  for first in [{'finish_reason':'length','message':{'content':'{"ok":'}},{'finish_reason':'stop','message':{'content':''}}]:
   c=self.client()
   with patch.object(c,'_request',side_effect=[{'choices':[first]},{'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}]) as request:
    self.assertEqual(c.call('Return JSON evidence'),{'ok':True})
    self.assertEqual(request.call_count,2)
    self.assertEqual(request.call_args.args[1]['thinking'],{'type':'disabled'})
 def test_never_accept_truncated_after_retry(self):
  c=self.client()
  with patch.object(c,'_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}) as request:
   with self.assertRaisesRegex(ValueError,'截断'):c.call('JSON')
   self.assertEqual(request.call_count,2)

class RemovedLocalToolsTests(unittest.TestCase):
 def test_legacy_cli_configuration_cannot_invoke_any_model(self):
  for provider in ['codex','claude']:
   client=ModelClient({'provider':provider,'model':'fixture','api_key':'old-key'})
   with patch.object(client,'_request') as request:
    with self.assertRaisesRegex(ValueError,'仅支持模型API'):client.call('fixture')
    request.assert_not_called()
   with tempfile.TemporaryDirectory() as d:
    with self.assertRaisesRegex(ValueError,'仅支持模型API'):SettingsStore(Path(d)/'settings.json').save({'provider':provider,'model':'fixture'})

class GoogleGeminiTests(unittest.TestCase):
 def test_save_google_default_endpoint_and_secret(self):
  with tempfile.TemporaryDirectory() as d:
   store=SettingsStore(Path(d)/'settings.json')
   public=store.save({'provider':'google','model':'gemini-test','api_key':'google-secret'})
   self.assertEqual(public['base_url'],'https://generativelanguage.googleapis.com/v1beta/openai')
   self.assertNotIn('google-secret',json.dumps(public))
 def test_google_connection_and_json_review_protocol(self):
  client=ModelClient({'provider':'google','model':'gemini-test','api_key':'google-secret'})
  with patch.object(client,'_request',return_value={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}) as request:
   self.assertTrue(client.test()['ok'])
   url,payload,headers,cancel=request.call_args.args
   self.assertEqual(url,'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
   self.assertEqual(headers['Authorization'],'Bearer google-secret')
   self.assertEqual(payload['response_format'],{'type':'json_object'})
   self.assertEqual(payload['model'],'gemini-test')
 def test_google_truncation_rejected(self):
  client=ModelClient({'provider':'google','model':'gemini-test','api_key':'test'})
  with patch.object(client,'_request',return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}):
   with self.assertRaisesRegex(ValueError,'截断'):client.call('Return JSON')

class ProviderIsolationTests(unittest.TestCase):
 def test_google_cannot_send_to_deepseek(self):
  client=ModelClient({'provider':'google','model':'gemini-test','api_key':'secret','base_url':'https://api.deepseek.com'})
  with patch.object(client,'_request') as request:
   with self.assertRaisesRegex(ValueError,'不一致'):client.call('test')
   request.assert_not_called()
 def test_switch_provider_never_reuses_old_key(self):
  with tempfile.TemporaryDirectory() as d:
   store=SettingsStore(Path(d)/'m')
   store.save({'provider':'deepseek','model':'test','api_key':'old-key'})
   store.save({'provider':'google','model':'gemini-test','api_key':''})
   self.assertEqual(store.snapshot()['api_key'],'')
 def test_google_settings_reject_wrong_address(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'不一致'):SettingsStore(Path(d)/'m').save({'provider':'google','model':'gemini-test','base_url':'https://api.deepseek.com','api_key':'test'})

class EfficientPipelineTests(unittest.TestCase):
 def test_pipeline_invalid_json_is_not_automatically_resent(self):
  c=ModelClient({'provider':'deepseek','model':'deepseek-flash','api_key':'test','_output_limit':6000,'_purpose':'review'})
  with patch.object(c,'_request',return_value={'choices':[{'finish_reason':'stop','message':{'content':'invalid'}}]}) as request:
   with self.assertRaises(ValueError):c.call('JSON')
   self.assertEqual(request.call_count,1);self.assertEqual(request.call_args.args[1]['max_tokens'],6000);self.assertEqual(request.call_args.args[1]['thinking'],{'type':'disabled'})
