import base64,unittest
import test_automatic_review as fixtures
from pdf_fixture import make_pdf
from app.evidence import normalized
from app.evidence_identity import supplied_texts

class CrossBlockTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def fixture(self):
  path=make_pdf(self.root/'lines.pdf',pages=[[(50,730,'Smith 2023 Attention Study'),(50,700,'Training improved recall'),(50,680,'in adults after practice.')]])
  source=self.assets.upload('lines.pdf',base64.b64encode(path.read_bytes()).decode());source=self.assets.confirm(source['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  task=self.tasks.create('Training improved recall (Smith, 2023).',[source]);package=self.evidence.prepare(task['id']);sid=source['id'];index=package['sources'][sid]
  blocks=index['pages'][0]['blocks']
  evidence=dict(source_id=sid,pdf_sha256=index['sha256'],block_id=blocks[1]['id'],quote='Training improved recall in adults after practice.',role='支持')
  return package,sid,blocks,evidence
 def test_adjacent_pdf_lines_verify_and_highlight_both_lines(self):
  package,sid,blocks,evidence=self.fixture();verified=self.evidence.verify_evidence(package,sid,evidence)
  self.assertEqual(verified['validation'],'verified');self.assertEqual(normalized(verified['quote']),evidence['quote'])
  self.assertEqual(len(verified['block_ids']),2);self.assertGreaterEqual(len(verified['regions']),2)
  self.assertEqual(self.evidence.verify_evidence(package,sid,verified)['validation'],'verified')
 def test_does_not_invent_words_or_cross_wrong_fingerprint(self):
  package,sid,blocks,evidence=self.fixture()
  for change in [dict(quote='Training improved recall in children.'),dict(pdf_sha256='0'*64)]:
   with self.assertRaises(ValueError):self.evidence.verify_evidence(package,sid,{**evidence,**change})
 def test_candidate_scope_requires_every_contiguous_block(self):
  package,sid,blocks,evidence=self.fixture()
  source=dict(id=sid,blocks=blocks[1:]);texts=supplied_texts(package,source)
  self.assertTrue(any(normalized(evidence['quote']) in normalized(text) for text in texts))
  source['blocks']=[blocks[1]];self.assertFalse(any(normalized(evidence['quote']) in normalized(text) for text in supplied_texts(package,source)))
