import hashlib,tempfile,unittest
from pathlib import Path
from app.sources import AssetStore
class IdentityReuseTests(unittest.TestCase):
 def test_same_bytes_reuses_without_model(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);store=AssetStore(root);p=root/'paper.pdf';p.write_bytes(b'%PDF-same');sha=hashlib.sha256(p.read_bytes()).hexdigest()
   known=dict(id='a'*32,path=str(p),sha256=sha,title='Study',authors='Lan',year='2022',metadata_verified=True,metadata_source='model_verified_in_pdf',attachment_status='available')
   unknown={**known,'id':'b'*32,'authors':'','metadata_verified':False,'metadata_attempt':{'state':'failed'}}
   store.save(known);store.save(unknown);row=store.get(unknown['id']);self.assertTrue(row['metadata_verified']);self.assertEqual(row['authors'],'Lan');self.assertNotIn('metadata_attempt',row)
   self.assertTrue(AssetStore(root).get(unknown['id'])['metadata_verified'])
 def test_conflict_or_changed_bytes_not_reused(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);store=AssetStore(root);p=root/'one.pdf';p.write_bytes(b'%PDF-one');sha=hashlib.sha256(p.read_bytes()).hexdigest()
   a=dict(id='a'*32,path=str(p),sha256=sha,title='Study',authors='Lan',year='2022',metadata_verified=True,attachment_status='available')
   b={**a,'id':'b'*32,'year':'2023'};u={**a,'id':'c'*32,'authors':'','metadata_verified':False}
   for row in [a,b,u]:store.save(row)
   self.assertFalse(store.get(u['id'])['metadata_verified'])
   store.meta_path(b['id']).unlink();p.write_bytes(b'%PDF-changed');self.assertFalse(store.get(u['id'])['metadata_verified'])
