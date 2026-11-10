import unittest
from app.citations import extract_locations
class CitationScopeTests(unittest.TestCase):
 def test_successive_citations_have_separate_claims(self):
  text='患病率22%（Xiao et al., 2022），与抑郁焦虑相关（Wang et al., 2022）。'
  a,b=extract_locations(text)['locations']
  self.assertEqual(a['claim_text'],'患病率22%（Xiao et al., 2022）')
  self.assertEqual(b['claim_text'],'与抑郁焦虑相关（Wang et al., 2022）。')
  self.assertEqual(a['sentence'],text)
  self.assertEqual(b['sentence'],text)
 def test_grouped_sources_become_independent_review_units(self):
  text='论点（Brown & Plener, 2017；Wang et al., 2022），补充描述。'
  rows=extract_locations(text)['locations']
  self.assertEqual(len(rows),2);self.assertTrue(all(r['claim_text']==text for r in rows))
  self.assertTrue(all(len(r['members'])==1 for r in rows))
  self.assertEqual(rows[0]['citation_group_id'],rows[1]['citation_group_id'])
