import copy,unittest
import test_automatic_review as fixtures
from app.evidence_identity import bind_generated_identity

class IdentityTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def fixture(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  task=self.tasks.create('Training improved recall (Smith, 2023).',[self.s]);package=self.evidence.prepare(task['id']);sid=self.s['id'];index=package['sources'][sid];block=index['pages'][0]['blocks'][-1]
  source=dict(id=sid,sha256=index['sha256'],blocks=[block])
  evidence=dict(source_id=sid,pdf_sha256=index['sha256'][:24],block_id=block['id'],quote=block['text'],role='支持')
  row=dict(claims=[dict(source_judgments=[dict(source_id=sid,evidence=[evidence])])])
  return package,sid,source,row
 def test_malformed_echo_recovered_only_from_supplied_verified_block(self):
  package,sid,source,row=self.fixture();before=copy.deepcopy(row)
  fixed=bind_generated_identity(row,[source],{sid},self.evidence.verify_evidence,package)
  e=fixed['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(e['pdf_sha256'],source['sha256']);self.assertEqual(row,before)
  self.assertEqual(self.evidence.verify_evidence(package,sid,e)['validation'],'verified')
  with self.assertRaisesRegex(ValueError,'指纹'):self.evidence.verify_evidence(package,sid,before['claims'][0]['source_judgments'][0]['evidence'][0])
 def test_wrong_full_fingerprint_and_other_source_are_never_rebound(self):
  for change in [dict(pdf_sha256='0'*64),dict(source_id='other')]:
   package,sid,source,row=self.fixture();row['claims'][0]['source_judgments'][0]['evidence'][0].update(change)
   self.assertEqual(bind_generated_identity(row,[source],{sid},self.evidence.verify_evidence,package),row)
 def test_mistyped_offset_recovers_only_unique_supplied_quote(self):
  package,sid,source,row=self.fixture()
  row['claims'][0]['source_judgments'][0]['evidence'][0]['block_id']=source['sha256'][:16]+'-p1-c999-9999'
  fixed=bind_generated_identity(row,[source],{sid},self.evidence.verify_evidence,package)
  e=fixed['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(e['block_id'],source['blocks'][0]['id'])
  self.assertEqual(self.evidence.verify_evidence(package,sid,e)['validation'],'verified')
  duplicate=copy.deepcopy(source);duplicate['blocks'].append({**source['blocks'][0],'id':source['sha256'][:16]+'-p2-c0-99'})
  self.assertEqual(bind_generated_identity(row,[duplicate],{sid},self.evidence.verify_evidence,package),row)
 def test_pdf_discretionary_hyphen_keeps_original_character_mapping(self):
  from app.evidence import normalize_map,normalized
  raw='we identi\x02fied a repetitive pat\x02tern'
  value,mapping=normalize_map(raw)
  self.assertEqual(value,'we identified a repetitive pattern')
  start=value.index('identified');end=start+len('identified')
  self.assertEqual(raw[mapping[start][0]:mapping[end-1][1]],'identi\x02fied')
  self.assertNotEqual(normalized('56.4%'),normalized('65.4%'))
 def test_unicode_ligature_and_typographic_punctuation_normalize_with_offsets(self):
  from app.evidence import normalize_map,normalized
  raw='The ﬁnding—was “supported”.';value,mapping=normalize_map(raw)
  self.assertEqual(value,'The findingwas "supported".')
  start=value.index('finding');end=start+len('finding')
  self.assertEqual(raw[mapping[start][0]:mapping[end-1][1]],'ﬁnding')
  self.assertEqual(normalized('ﬁnding—supported'),normalized('finding-supported'))
  self.assertEqual(normalized('self\x02injurious behavior'),normalized('self-injurious behavior'))
 def test_missing_ids_recover_from_unique_supplied_quote(self):
  package,sid,source,row=self.fixture();e=row['claims'][0]['source_judgments'][0]['evidence'][0]
  e.pop('pdf_sha256');e.pop('block_id');e.pop('source_id')
  fixed=bind_generated_identity(row,[source],{sid},self.evidence.verify_evidence,package)
  recovered=fixed['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(recovered['source_id'],sid);self.assertEqual(recovered['block_id'],source['blocks'][0]['id'])
  self.assertEqual(self.evidence.verify_evidence(package,sid,recovered)['validation'],'verified')
 def test_invented_quote_cannot_recover(self):
  package,sid,source,row=self.fixture();row['claims'][0]['source_judgments'][0]['evidence'][0]['quote']='Invented evidence'
  self.assertEqual(bind_generated_identity(row,[source],{sid},self.evidence.verify_evidence,package),row)
