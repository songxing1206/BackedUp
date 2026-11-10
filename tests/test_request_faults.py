import io,json,socket,tempfile,threading,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch,Mock
from app.model_provider import ModelClient

class RequestFaultTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict('os.environ',{'BACKEDUP_DATA_HOME':self.temp.name});self.env.start()
  self.client=ModelClient({'provider':'openai','model':'fixture-only','api_key':'private-fixture','base_url':'https://api.openai.com/v1'})
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def run_error(self,error,testing=False):
  if testing:self.client.settings['_purpose']='connection_test'
  opener=Mock();opener.open.side_effect=error;cancel=Mock();cancel.is_set.return_value=False;cancel.wait.return_value=False
  with patch('app.model_provider.urllib.request.build_opener',return_value=opener):
   with self.assertRaises(ValueError) as failure:self.client.call('fictional input',cancel)
  return opener,cancel,str(failure.exception)
 def test_auth_does_not_retry_or_fallback(self):
  error=urllib.error.HTTPError('https://api.openai.com',401,'no',{},io.BytesIO())
  opener,_,message=self.run_error(error);self.assertEqual(opener.open.call_count,1);self.assertIn('鉴权',message)
  request=opener.open.call_args.args[0];self.assertTrue(request.full_url.startswith('https://api.openai.com/'));self.assertEqual(json.loads(request.data)['model'],'fixture-only')
 def test_rate_limit_and_server_error_bounded(self):
  for code in [429,503]:
   opener,cancel,_=self.run_error(urllib.error.HTTPError('https://api.openai.com',code,'no',{},io.BytesIO()));self.assertEqual(opener.open.call_count,3);self.assertEqual(cancel.wait.call_count,2)
 def test_connection_test_does_not_retry(self):
  opener,_,_=self.run_error(urllib.error.HTTPError('https://api.openai.com',429,'no',{},io.BytesIO()),True);self.assertEqual(opener.open.call_count,1)
 def test_network_and_timeout_are_terminal(self):
  for error in [urllib.error.URLError('offline'),socket.timeout()]:
   opener,_,message=self.run_error(error);self.assertEqual(opener.open.call_count,1);self.assertIn('超时' if isinstance(error,socket.timeout) else '中断',message)
 def test_cancel_during_retry_starts_no_more_requests(self):
  opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://api.openai.com',503,'no',{},io.BytesIO());cancel=Mock();cancel.is_set.return_value=False;cancel.wait.return_value=True
  with patch('app.model_provider.urllib.request.build_opener',return_value=opener):
   with self.assertRaisesRegex(ValueError,'取消'):self.client.call('fictional',cancel)
  self.assertEqual(opener.open.call_count,1)
 def test_audit_in_user_directory_has_no_key_or_prompt(self):
  self.client._audit('https://api.openai.com/v1/chat/completions',{'model':'fixture-only','messages':['fictional confidential manuscript']},'started')
  text=(Path(self.temp.name)/'data-v1/logs/api-requests.jsonl').read_text();self.assertNotIn('private-fixture',text);self.assertNotIn('manuscript',text);self.assertIn('fixture-only',text)
