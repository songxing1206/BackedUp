import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
from test_evidence_http import HttpTests
from app.model_settings import SettingsStore
class ReviewHttp(HttpTests):
 def test_model_settings_secret_and_csrf(self):
  with tempfile.TemporaryDirectory() as d,patch('server.model_settings',SettingsStore(Path(d)/'m')):
   status,_=self.request('POST','/api/model/settings',{'provider':'deepseek','model':'test','api_key':'private'},False);self.assertEqual(status,403)
   status,body=self.request('POST','/api/model/settings',{'provider':'deepseek','model':'test','api_key':'private'});self.assertEqual(status,200);self.assertNotIn(b'private',body)
   status,body=self.request('GET','/api/model/settings');self.assertEqual(status,200);self.assertTrue(json.loads(body)['has_key'])
 def test_task_pdf_page_ownership(self):
  tid=self.env.t['id'];sid=self.env.s[0]['id'];status,body=self.request('GET',f'/api/tasks/{tid}/sources/{sid}/pages/0');self.assertEqual(status,200);self.assertTrue(body.startswith(b'\x89PNG'))
  status,_=self.request('GET',f'/api/tasks/{tid}/sources/{"a"*32}/pages/0');self.assertEqual(status,400)
 def test_server_import_does_not_touch_live_jobs(self):
  import server
  self.assertIsNone(server.checks)
 def test_jobs_contract_and_cancel(self):
  import server
  class FakeQueue:
   def start(_,text,ids,task_id=None):return {'id':'a'*32,'status':'queued','text':text,'task_id':task_id}
   def get(_,id):return {'id':id,'status':'running','text':'private manuscript'}
   def cancel(_,id):return {'id':id,'status':'cancelled'}
  with patch('server.checks',FakeQueue()):
   status,body=self.request('POST','/api/checks',{'text':'claim','source_ids':['b'*32]});self.assertEqual(status,200);self.assertNotIn('text',json.loads(body))
   status,body=self.request('GET','/api/checks/'+'a'*32);self.assertEqual(status,200);self.assertNotIn(b'private manuscript',body)
   status,body=self.request('POST','/api/checks/'+'a'*32+'/cancel',{});self.assertEqual(json.loads(body)['status'],'cancelled')
