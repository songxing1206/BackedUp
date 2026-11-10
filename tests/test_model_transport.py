import io,json,threading,time,unittest
from unittest.mock import patch
from app.model_transport import read_completion,ReviewHTTPSHandler,RESPONSE_TIMEOUT
from app.model_provider import ModelClient,ModelConnectionError

class Response(io.BytesIO):
 def __init__(self,body,kind='text/event-stream'):
  super().__init__(body);self.headers={'Content-Type':kind};self.status=200

def event(row):return ('data: '+json.dumps(row,ensure_ascii=False)+'\n\n').encode()

class StreamTests(unittest.TestCase):
 def test_valid_reply_after_old_120_second_limit_is_accepted(self):
  body=event({'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':'stop'}]})+b'data: [DONE]\n\n'
  progress={}
  row=read_completion(Response(body),threading.Event(),time.monotonic()-121,progress)
  self.assertEqual(json.loads(row['choices'][0]['message']['content']),{'ok':True})
  self.assertGreaterEqual(progress['model_output_seconds'],121)
 def test_heartbeats_reasoning_unicode_and_usage(self):
  body=b': keep-alive\n\n'+event({'choices':[{'delta':{'reasoning_content':'private thinking'}}]})
  for text in ['{"answer":','"支持"}']:
   body+=event({'choices':[{'index':0,'delta':{'content':text}}]})
  body+=event({'choices':[{'delta':{},'finish_reason':'stop'}]})
  body+=event({'choices':[],'usage':{'total_tokens':123}})+b'data: [DONE]\n\n'
  progress={};row=read_completion(Response(body),threading.Event(),time.monotonic(),progress)
  self.assertEqual(json.loads(row['choices'][0]['message']['content']),{'answer':'支持'})
  self.assertEqual(row['usage']['total_tokens'],123);self.assertEqual(progress['usage'],row['usage'])
  self.assertNotIn('private',json.dumps(row));self.assertIn('first_byte_seconds',progress)
 def test_json_gateway_fallback(self):
  self.assertEqual(read_completion(Response(b'{"ok":true}','application/json'),threading.Event(),time.monotonic(),{}),{'ok':True})
 def test_missing_done_is_not_success_even_with_complete_json(self):
  import http.client
  with self.assertRaises(http.client.RemoteDisconnected):
   read_completion(Response(event({'choices':[{'delta':{'content':'{}'}}]})),threading.Event(),time.monotonic(),{})
 def test_cancel_and_total_deadline(self):
  cancel=threading.Event();cancel.set()
  with self.assertRaisesRegex(ValueError,'取消'):read_completion(Response(b''),cancel,time.monotonic(),{})
  with self.assertRaises(TimeoutError):read_completion(Response(b''),threading.Event(),time.monotonic()-RESPONSE_TIMEOUT-1,{})
 def test_disconnect_after_usage_preserves_accounting(self):
  client=ModelClient(dict(provider='custom',model='test',api_key='fixture',base_url='https://example.invalid/v1',_output_limit=6000))
  body=event({'choices':[],'usage':{'total_tokens':99}})
  with patch('urllib.request.build_opener') as opener,patch.object(client,'_audit') as audit:
   opener.return_value.open.return_value=Response(body)
   with self.assertRaises(ModelConnectionError):client.call('JSON')
   self.assertEqual(client.last_usage,{'total_tokens':99})
   self.assertEqual(audit.call_args.kwargs['phase'],'reading_response')
   self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],600)
 def test_long_review_uses_stream_but_short_probe_does_not(self):
  client=ModelClient(dict(provider='custom',model='test',api_key='fixture',base_url='https://example.invalid/v1'))
  with patch.object(client,'_request',return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}) as call:
   client.call('JSON');self.assertTrue(call.call_args.args[1]['stream'])
   client.test();self.assertNotIn('stream',call.call_args.args[1])
 def test_connect_and_response_timeouts_are_separate(self):
  progress={};handler=ReviewHTTPSHandler(progress)
  with patch.object(handler,'do_open') as open_,patch('http.client.HTTPSConnection.connect') as connect:
   handler.https_open(object());cls=open_.call_args.args[0];connection=cls('example.invalid',timeout=600)
   from unittest.mock import Mock
   connection.sock=Mock();connection.connect()
   self.assertEqual(connection.timeout,30);connection.sock.settimeout.assert_called_once_with(600)
   self.assertEqual(progress['phase'],'waiting_headers')
