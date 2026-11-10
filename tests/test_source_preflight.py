import tempfile,unittest,json
from pathlib import Path
from app.source_preflight import source_preflight
import test_automatic_review as fixtures
from app.automatic_review import ReviewQueue

class SourcePreflightTests(unittest.TestCase):
 def test_separate_missing_identity_and_encrypted(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'paper.pdf';p.write_bytes(b'%PDF-')
   sources=[dict(id='one',filename='locked.pdf',authors='Smith',year='2023',metadata_verified=True,attachment_status='unreadable',warnings=['PDF需要密码']),dict(id='two',filename='unknown.pdf',authors='',year='',metadata_verified=False,attachment_status='available',path=str(p))]
   r=source_preflight('Claim (Smith, 2023). Other (Jones, 2022).',sources)
   self.assertEqual(r['model_calls'],0);self.assertEqual(r['readable_files'],1)
   self.assertIn('encrypted',[i['kind'] for i in r['issues']]);self.assertIn('missing_source',[i['kind'] for i in r['issues']]);self.assertNotIn('identity_unconfirmed',[i['kind'] for i in r['issues']])
   self.assertTrue(any(i['kind']=='missing_source' and i['action']=='upload_pdf' for i in r['issues']))
 def test_selected_scope_and_missing_disk_file(self):
  s=dict(id='one',authors='Smith',year='2023',metadata_verified=True,attachment_status='available',path='/nonexistent/paper.pdf')
  r=source_preflight('A (Smith, 2023). B (Jones, 2022).',[s],1)
  self.assertEqual(r['locations'],1);self.assertEqual(r['ready_locations'],0);self.assertEqual(r['issues'][0]['kind'],'missing_file')
 def test_missing_ambiguous_and_identity_conflict_have_distinct_actions(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'paper.pdf';p.write_bytes(b'%PDF-')
   base=dict(attachment_status='available',path=str(p),metadata_verified=True)
   sources=[dict(id='a',title='A',authors='Smith',year='2023',**base),dict(id='b',title='B',authors='Smith',year='2023',**base),dict(id='c',title='C',authors='Jane Doe',year='2022',**base)]
   result=source_preflight('A (Smith, 2023). B (Doe, 2022). C (Missing, 2020).',sources)
   by_label={i['label']:i for i in result['issues'] if i.get('location_id')}
   self.assertEqual(by_label['C001 · Smith, 2023']['kind'],'ambiguous_source')
   self.assertEqual(by_label['C001 · Smith, 2023']['action'],'select_candidate')
   self.assertEqual(by_label['C002 · Doe, 2022']['kind'],'identity_conflict')
   self.assertEqual(by_label['C002 · Doe, 2022']['action'],'resolve_identity')
   self.assertEqual(by_label['C003 · Missing, 2020']['kind'],'missing_source')
   self.assertEqual(by_label['C003 · Missing, 2020']['action'],'upload_pdf')
 def test_unique_leading_filename_hint_is_ready_without_duplicate_warning(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'Lutz 2022.pdf';p.write_bytes(b'%PDF-')
   source=dict(id='lutz',filename='Lutz 2022锛圢SSI-寮鸿揩鎬э級.pdf',authors='',year='',metadata_verified=False,attachment_status='available',path=str(p))
   result=source_preflight('Claim (Lutz et al., 2022).',[source])
   self.assertEqual(result['ready_locations'],1)
   self.assertFalse(any(i.get('location_id') for i in result['issues']))
   self.assertFalse(any(i.get('kind')=='identity_unconfirmed' for i in result['issues']))
 def test_plain_author_match_with_wrong_year_requests_correct_pdf(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'Nock 2009.pdf';p.write_bytes(b'%PDF-')
   source=dict(id='nock',filename='Nock 2009.pdf',title='Why Do People Hurt Themselves?',authors='Nock',year='2009',metadata_verified=True,attachment_status='available',path=str(p))
   result=source_preflight('Claim (Nock et al., 2008).',[source])
   issue=next(i for i in result['issues'] if i.get('location_id'))
   self.assertEqual(issue['kind'],'year_mismatch');self.assertEqual(issue['action'],'upload_pdf')
   self.assertIn('2008',issue['advice']);self.assertIn('2009',issue['advice'])

class UnreadableQueueTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def test_unreadable_source_does_not_abort_readable_source(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  locked=self.root/'locked.pdf';locked.write_bytes(b'%PDF-locked-test')
  bad={**self.s,'id':'b'*32,'filename':'locked.pdf','attachment_status':'unreadable','warnings':['PDF需要密码'],'metadata_verified':False,'sha256':'f'*64,'path':str(locked)}
  self.assets.save(bad)
  calls=[]
  class Fake:
   def call(_,p,e):calls.append(p);raise AssertionError('no matching candidate, no API')
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  try:
   j=q.start('Quantum mechanics (Smith, 2023).',[self.s['id'],bad['id']]);q.wait(j['id'],5);r=q.get(j['id'])
   self.assertEqual(r['status'],'partial');self.assertIsNotNone(r['task_id']);self.assertTrue(any('密码' in e for e in r['errors']));self.assertEqual(calls,[])
  finally:q.close()
