import unittest,tempfile
from pathlib import Path
from app.retrieval import Retriever,pack_sources,query_terms,numeric_score
from app.request_budget import reserve,BudgetExceeded

class RetrievalTests(unittest.TestCase):
 def index(self):
  return {'sha256':'f'*64,'pages':[{'physical_page':1,'blocks':[{'id':'definition','text':'Non suicidal self injury is direct repetitive injury without suicidal intent.'},{'id':'other','text':'Basketball is played on a court.'}]}]}
 def test_chinese_terms_retrieve_original_ids_and_cache_on_disk(self):
  with tempfile.TemporaryDirectory() as d:
   r=Retriever(d);path=r.build(self.index());before=path.stat().st_mtime_ns
   blocks=r.select(path,'非自杀性自伤是没有自杀意图的重复行为')
   self.assertIn('definition',[b['id'] for b in blocks]);self.assertEqual(r.build(self.index()).stat().st_mtime_ns,before)
 def test_unknown_query_does_not_guess_or_send_whole_paper(self):
  with tempfile.TemporaryDirectory() as d:
   r=Retriever(d);self.assertEqual(r.select(r.build(self.index()),'量子纠缠'),[])
 def test_c002_numeric_result_enters_candidate_set(self):
  index={'sha256':'2'*64,'pages':[{'physical_page':1,'blocks':[{'id':'background','text':'Participants reported repeated NSSI.'}]},{'physical_page':5,'blocks':[{'id':'reichl-result','text':'The frequency of NSSI in the six months before baseline ranged between five and 180 with a mean of 52.19 days.'}]}]}
  claim='During the six months before treatment, NSSI occurred on average 52 days, with a maximum of 180 days.'
  with tempfile.TemporaryDirectory() as d:
   selected=Retriever(d).select(Retriever(d).build(index),claim)
   self.assertIn('reichl-result',[b['id'] for b in selected])
  self.assertGreater(numeric_score(claim,index['pages'][1]['blocks'][0]['text']),0)
 def test_budget_pack_does_not_truncate_quotes(self):
  source={'id':'a','blocks':[{'id':'huge','text':'x'*10000},{'id':'short','text':'real sentence'}]}
  packed=pack_sources([source],200);self.assertEqual(packed[0]['blocks'],[source['blocks'][1]])
 def test_request_reservation_precedes_spending(self):
  job={'max_requests':1,'token_budget':100}
  reserve(job,60,40)
  with self.assertRaises(BudgetExceeded):reserve(job,1,1)
  self.assertEqual(job['budget_usage']['requests'],1)

 def test_unlimited_still_records_usage(self):
  job={'max_requests':None,'token_budget':None}
  for _ in range(301):reserve(job,1000000,65536)
  self.assertEqual(job['budget_usage']['requests'],301)
  self.assertGreater(job['budget_usage']['reserved_tokens'],2000000)
