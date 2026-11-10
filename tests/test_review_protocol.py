import unittest
from app.agent.protocol import normalize_review_response


def judgment(source='S1',status='支持',evidence=True):
 return dict(source_id=source,status=status,reason='model reason',evidence=[dict(source_id=source,quote='verbatim',role='support')] if evidence else [])


class ReviewProtocolTests(unittest.TestCase):
 def test_explicit_status_and_role_aliases(self):
  row=dict(claims=[dict(id='P1',text='claim',source_judgments=[judgment(status='partial')])],combined=dict(status='partial',reason='limited'))
  fixed=normalize_review_response(row,{'S1'});j=fixed['claims'][0]['source_judgments'][0]
  self.assertEqual(j['status'],'部分支持');self.assertEqual(j['evidence'][0]['role'],'支持')
  self.assertEqual(fixed['combined']['status'],'部分支持');self.assertEqual(row['combined']['status'],'partial')
 def test_missing_role_is_derived_only_for_unambiguous_status(self):
  supported=judgment();supported['evidence'][0].pop('role')
  partial=judgment('S2','部分支持');partial['evidence'][0].pop('role')
  fixed=normalize_review_response(dict(claims=[dict(id='P1',text='claim',source_judgments=[supported,partial])],combined=dict(status='部分支持',reason='mixed')),{'S1','S2'})
  self.assertEqual(fixed['claims'][0]['source_judgments'][0]['evidence'][0]['role'],'支持')
  self.assertNotIn('role',fixed['claims'][0]['source_judgments'][1]['evidence'][0])
 def test_missing_top_level_is_aggregated_only_from_complete_matrix(self):
  claims=[dict(id='P1',text='claim',source_judgments=[judgment('S1'),judgment('S2','部分支持')])]
  fixed=normalize_review_response(dict(claims=claims),{'S1','S2'})
  self.assertEqual(fixed['combined']['status'],'部分支持');self.assertEqual(fixed['combined']['aggregation'],'complete_judgment_matrix')
  incomplete=normalize_review_response(dict(claims=claims),{'S1','S2','S3'})
  self.assertNotIn('status',incomplete['combined'])
 def test_missing_evidence_downgrades_only_that_judgment(self):
  claims=[dict(id='P1',text='claim',source_judgments=[judgment('S1'),judgment('S2','部分支持',False)])]
  fixed=normalize_review_response(dict(claims=claims,combined=dict(status='支持',reason='model')),{'S1','S2'})
  rows=fixed['claims'][0]['source_judgments'];self.assertEqual(rows[0]['status'],'支持');self.assertEqual(rows[1]['status'],'无法判断')
  self.assertEqual(rows[1]['protocol_error'],'required_evidence_missing');self.assertEqual(fixed['combined']['status'],'无法判断')
 def test_not_in_paper_is_not_promoted_to_unsupported(self):
  row=dict(claims=[dict(id='P1',text='claim',source_judgments=[judgment(status='not_in_paper')])],combined=dict(status='not_in_paper',reason='not found'))
  fixed=normalize_review_response(row,{'S1'})
  self.assertEqual(fixed['claims'][0]['source_judgments'][0]['status'],'无法判断');self.assertEqual(fixed['combined']['status'],'无法判断')
 def test_unknown_label_is_not_guessed(self):
  row=dict(claims=[dict(id='P1',text='claim',source_judgments=[judgment(status='maybe_yes')])],combined=dict(status='maybe_yes',reason='ambiguous'))
  fixed=normalize_review_response(row,{'S1'})
  self.assertEqual(fixed['combined']['status'],'maybe_yes');self.assertEqual(fixed['claims'][0]['source_judgments'][0]['status'],'maybe_yes')


if __name__=='__main__':unittest.main()
