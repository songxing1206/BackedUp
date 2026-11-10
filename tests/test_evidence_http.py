import io,json,unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_evidence
import server
class MemoryRequest:
 def __init__(self,data):self.input=io.BytesIO(data);self.output=bytearray()
 def makefile(self,*args):return self.input
 def sendall(self,data):self.output.extend(data)
class HttpTests(unittest.TestCase):
 def setUp(self):self.env=test_evidence.EvidenceTests();self.env.setUp()
 def tearDown(self):self.env.tearDown()
 def request(self,method,path,data=None,token=True):
  body=json.dumps(data).encode() if data is not None else b'';headers=f'{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:8787\r\nConnection: close\r\nContent-Length: {len(body)}\r\n'
  if token:headers+=f'X-BackedUp-Token: {server.TOKEN}\r\n'
  request=MemoryRequest(headers.encode()+b'\r\n'+body)
  with patch.multiple(server,tasks=self.env.tasks,assets=self.env.assets,evidence=self.env.service):server.Handler(request,('127.0.0.1',1234),SimpleNamespace(server_port=8787))
  head,content=bytes(request.output).split(b'\r\n\r\n',1);return int(head.split()[1]),content
 def test_prepare_and_unauthorized(self):
  path='/api/tasks/'+self.env.t['id']+'/evidence/prepare'
  status,_=self.request('POST',path,{},token=False);self.assertEqual(status,403)
  status,body=self.request('POST',path,{});self.assertEqual(status,200);self.assertTrue(json.loads(body)['sources'])
 def test_import_preview_unknown(self):
  tid=self.env.t['id'];status,body=self.request('POST',f'/api/tasks/{tid}/evidence/import',self.env.result());self.assertEqual(status,200)
  task=json.loads(body);e=task['evidence_review']['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0]
  status,body=self.request('GET',f'/api/tasks/{tid}/evidence/{e["id"]}/page');self.assertEqual(status,200);self.assertTrue(body.startswith(b'\x89PNG'))
  status,_=self.request('GET',f'/api/tasks/{tid}/evidence/{"a"*32}/page');self.assertEqual(status,400)
 def test_foreign_source_import_rejected(self):
  data=self.env.result();data['locations'][0]['claims'][0]['source_judgments'][0]['source_id']='foreign';status,_=self.request('POST',f'/api/tasks/{self.env.t["id"]}/evidence/import',data);self.assertEqual(status,400)
 def test_export_and_static(self):
  tid=self.env.t['id'];status,body=self.request('GET',f'/api/tasks/{tid}/evidence/prompt');self.assertEqual(status,200);self.assertIn('核查包'.encode(),body)
  status,body=self.request('GET',f'/api/tasks/{tid}/evidence/package');self.assertEqual(status,200);self.assertNotIn(b'"chars"',body)
 def test_document_preview(self):
  sid=self.env.t['sources'][0]['id'];status,body=self.request('GET',f'/api/assets/{sid}/document');self.assertEqual(status,200)
  preview=json.loads(body);self.assertEqual(preview['schema_version'],'document-1');self.assertIn('metadata',preview);self.assertIn('markdown',preview);self.assertNotIn('raw_text',preview)
