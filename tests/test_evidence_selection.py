import unittest,tempfile
from app.evidence_selection import focused_context,select_units,pack_units
from app.retrieval import Retriever

class SelectionTests(unittest.TestCase):
 def test_standalone_claim_has_no_unrelated_context(self):
  self.assertEqual(focused_context('OCD prevalence was 4%.','Unrelated claim (Jones, 2020).'), '')
 def test_same_sample_retains_antecedent(self):
  claim='The same sample was reanalysed.'
  self.assertEqual(focused_context(claim,'An EMA study recruited adolescents. '+claim),'An EMA study recruited adolescents.')
 def test_pack_units_is_atomic_and_deduplicates_overlap(self):
  a={'id':'a','text':'First sentence.'};b={'id':'b','text':'However, only a subgroup.'}
  sources=[{'id':'s','units':[{'blocks':[a,b]},{'blocks':[a,b]}]}]
  self.assertEqual(pack_units(sources,2000)[0]['blocks'],[a,b])
  self.assertEqual(pack_units(sources,50),[])
 def test_unknown_query_does_not_return_scope_only(self):
  index={'sha256':'c'*64,'pages':[{'physical_page':1,'blocks':[{'id':'x','text':'Methods and participants were described.'}]}]}
  with tempfile.TemporaryDirectory() as d:
   r=Retriever(d);self.assertEqual(select_units(r.build(index),'quantum entropy'),[])

 def test_uncertain_antecedent_keeps_existing_context(self):
  context="Prior study "*100
  self.assertEqual(focused_context("The same sample was reanalysed.",context),context)
