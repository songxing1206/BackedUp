import json,unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from app.metadata_checkpoint import resolve_metadata
from app.sources import AssetStore

class MetadataCheckpointTests(unittest.TestCase):
 def test_verified_response_persisted_before_validation_and_replays_without_request(self):
  with TemporaryDirectory() as d:
   store=AssetStore(Path(d));source={'id':'a'*32};calls=[]
   def verify(response,text):
    self.assertEqual(store.get(source['id'])['metadata_attempt']['response'],response)
    return dict(metadata_verified=True,title='Study')
   def request():calls.append(1);return {'title':'Study'}
   resolve_metadata(source,'sha','text',request,verify,store.save)
   recovered=store.get(source['id']);resolve_metadata(recovered,'sha','text',request,verify,store.save)
   self.assertEqual(calls,[1]);self.assertTrue(recovered['metadata_verified'])
 def test_failed_request_or_verification_is_never_automatically_charged_again(self):
  for failure in ['network','verification']:
   with self.subTest(failure=failure),TemporaryDirectory() as d:
    store=AssetStore(Path(d));source={'id':'b'*32};calls=[]
    def request():
     calls.append(1)
     if failure=='network':raise ValueError('network error')
     return {'title':'invalid'}
    def verify(response,text):raise ValueError('not exact')
    with self.assertRaises(ValueError):resolve_metadata(source,'sha','text',request,verify,store.save)
    recovered=store.get(source['id'])
    with self.assertRaisesRegex(ValueError,'停止重复自动调用'):resolve_metadata(recovered,'sha','text',request,verify,store.save)
    self.assertEqual(calls,[1])
 def test_interrupted_request_requires_manual_confirmation(self):
  source={'metadata_attempt':{'pdf_sha256':'sha','state':'requested'}}
  with self.assertRaisesRegex(ValueError,'手动确认'):resolve_metadata(source,'sha','',lambda:self.fail('paid again'),lambda r,t:{},lambda s:None)
 def test_changed_pdf_does_not_reuse_previous_response(self):
  source={'metadata_attempt':{'pdf_sha256':'old','state':'failed'}};calls=[]
  resolve_metadata(source,'new','',lambda:calls.append(1) or {},lambda r,t:{'metadata_verified':True},lambda s:None)
  self.assertEqual(calls,[1]);self.assertEqual(source['metadata_pdf_sha256'],'new')
