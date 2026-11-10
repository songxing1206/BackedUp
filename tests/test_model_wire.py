import unittest
from app.model_wire import encode,decode

class WireTests(unittest.TestCase):
 def setUp(self):
  self.data={'sources':[{'id':'long-source','sha256':'a'*64,'blocks':[{'id':'long-block','text':'Exact quote.'}]},{'id':'other-source','sha256':'b'*64,'blocks':[{'id':'other-block','text':'Other quote.'}]}]}
  self.wire,self.mapping=encode(self.data)
 def row(self,sid='S1',bid='B1',**extra):
  return {'claims':[{'source_judgments':[{'source_id':sid,'evidence':[{'source_id':sid,'block_id':bid,'quote':'Exact quote.',**extra}]}]}]}
 def test_short_refs_restore_provenance_without_changing_text(self):
  self.assertEqual(self.wire['sources'][0]['blocks'][0],{'id':'B1','text':'Exact quote.'})
  row=decode(self.row(),self.mapping);e=row['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(e,{'source_id':'long-source','block_id':'long-block','pdf_sha256':'a'*64,'quote':'Exact quote.'})
  self.assertEqual(self.data['sources'][0]['id'],'long-source')
 def test_wrong_source_block_pair_is_not_bound(self):
  e=decode(self.row(bid='B2'),self.mapping)['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(e['pdf_sha256'],'a'*64);self.assertEqual(e['block_id'],'B2')
 def test_missing_block_and_evidence_source_keep_unambiguous_enclosing_source(self):
  row=self.row();e=row['claims'][0]['source_judgments'][0]['evidence'][0];e.pop('block_id');e.pop('source_id')
  restored=decode(row,self.mapping)['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(restored['source_id'],'long-source');self.assertEqual(restored['pdf_sha256'],'a'*64);self.assertNotIn('block_id',restored)
 def test_conflicting_fingerprint_is_not_overwritten(self):
  e=decode(self.row(pdf_sha256='b'*64),self.mapping)['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(e['pdf_sha256'],'b'*64)
 def test_unknown_source_is_not_guessed(self):
  row=self.row('S9');self.assertEqual(decode(row,self.mapping),row)
 def test_no_sources_leaves_merge_or_metadata_unchanged(self):
  self.assertEqual(encode({'phase':'metadata','text':'PDF'}),({'phase':'metadata','text':'PDF'},{}))

from test_automatic_review import AutoTests
from app.automatic_review import ReviewQueue

class WireQueueTests(unittest.TestCase):
 setUp=AutoTests.setUp
 tearDown=AutoTests.tearDown
 def test_paid_adapter_references_are_restored_before_evidence_validation(self):
  self.s=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'));calls=[]
  class Fake:
   settings={'provider':'custom'}
   def call(_,prompt,event):
    import json
    data=json.loads(prompt.split('\nDATA\n')[1]);calls.append(data)
    source=data['sources'][0];block=source['blocks'][-1]
    return {'claims':[{'id':'P1','text':'Training improved recall','source_judgments':[{'source_id':source['id'],'status':'支持','reason':'verified','evidence':[{'source_id':source['id'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'verified'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda _:Fake())
  try:
   j=q.start('Training improved recall (Smith, 2023).',[self.s['id']],review_mode='deep');q.wait(j['id']);saved=q.get(j['id'])
   self.assertEqual(saved['status'],'completed');self.assertEqual(len(calls),1);self.assertEqual(calls[0]['sources'][0]['id'],'S1')
   row=self.tasks.get(saved['task_id'])['evidence_review']['locations'][0]
   self.assertEqual(row['claims'][0]['source_judgments'][0]['source_id'],self.s['id'])
  finally:q.close()
