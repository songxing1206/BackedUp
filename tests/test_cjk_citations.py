import unittest
from app.citations import extract_locations
class CjkCitationTests(unittest.TestCase):
 def test_fullwidth_group_keeps_offsets(self):
  text='研究发现（Brown & Plener, 2017；Wang et al., 2022）。另有发现（Xiao et al., 2022）。'
  rows=extract_locations(text)['locations'];self.assertEqual(len(rows),3)
  self.assertEqual([(r['members'][0]['author'],r['members'][0]['year']) for r in rows],[('Brown & Plener','2017'),('Wang et al.','2022'),('Xiao et al.','2022')])
  for r in rows:self.assertEqual(r['raw'],text[r['start']:r['end']])
 def test_chinese_narrative_suffix(self):
  text='Hasking等学者（2016）提出模型。Lan 等人（2022）进一步分析。'
  rows=extract_locations(text)['locations'];self.assertEqual([m['author'] for r in rows for m in r['members']],['Hasking','Lan'])
 def test_masked_code_stays_masked(self):
  self.assertFalse(extract_locations('`（Smith，2023）`')['locations'])
