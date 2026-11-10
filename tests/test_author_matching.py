import unittest
from app.matching import match_member, surname, diagnose_citation_year
from app.automatic_review import verify_metadata

class AuthorMatchingTests(unittest.TestCase):
 def source(self, authors, sid='one', year='2023'):
  return dict(id=sid, authors=authors, year=year, title=sid, metadata_verified=True, attachment_status='available')
 def match(self, author, *sources):
  return match_member(dict(author=author, year='2023'), list(sources))
 def test_compound_surnames_use_same_normalization(self):
  for name in ['de Mathis', 'van der Meer', 'García Márquez']:
   with self.subTest(name=name):
    self.assertEqual(self.match(name+' et al.', self.source(name))['status'], 'matched')
 def test_accents_and_unicode_are_equivalent(self):
  self.assertEqual(self.match('Penadés et al.', self.source('Penades'))['status'], 'matched')
  self.assertEqual(surname('Penade\u0301s'), surname('Penadés'))
 def test_given_name_only_proposes_candidate(self):
  r=self.match('Reddy et al.', self.source('Janardhan Reddy'))
  self.assertEqual(r['status'], 'needs_assignment');self.assertIsNone(r['source_id'])
  self.assertEqual([c['source_id'] for c in r['candidates']], ['one'])
 def test_given_name_is_not_treated_as_surname(self):
  self.assertEqual(self.match('Janardhan', self.source('Janardhan Reddy'))['status'], 'unmatched')
 def test_weak_candidate_does_not_hide_ambiguity(self):
  r=self.match('Reddy', self.source('Reddy','one'), self.source('Janardhan Reddy','two'))
  self.assertEqual(r['status'], 'needs_assignment');self.assertEqual(len(r['candidates']),2)
 def test_bibtex_family_name_is_exact(self):
  self.assertEqual(self.match('Reddy', self.source('Reddy, Janardhan and Smith, Jane'))['status'], 'matched')
 def test_institution_is_not_last_word_alias(self):
  self.assertEqual(self.match('Association',self.source('American Psychiatric Association'))['status'],'unmatched')
  self.assertEqual(self.match('American Psychiatric Association',self.source('American Psychiatric Association'))['status'],'matched')
 def test_year_suffix_and_verification_stay_required(self):
  mismatch=self.match('Reddy',self.source('Janardhan Reddy',year='2022'))
  self.assertEqual(mismatch['status'],'unmatched');self.assertEqual(mismatch['year_diagnosis']['status'],'mismatch')
  s=self.source('Penades');s['metadata_verified']=False
  self.assertEqual(self.match('Penadés',s)['status'],'needs_assignment')
  r=match_member(dict(author='Penadés',year='2023a'),[self.source('Penades',year='2023b')])
  self.assertEqual(r['status'],'needs_assignment');self.assertEqual(r['year_diagnosis']['status'],'ambiguous')
 def test_online_first_conflict_stays_ambiguous(self):
  source=self.source('Smith',year='2024');source.update(online_year='2023',publication_year='2024',metadata_source='bibtex')
  diagnosis=diagnose_citation_year({'year':'2023'},source)
  self.assertEqual(diagnosis['status'],'ambiguous');self.assertIn('Online First',diagnosis['reason'])
 def test_plain_year_difference_is_not_online_first_ambiguity(self):
  source=self.source('Nock',year='2009')
  diagnosis=diagnose_citation_year({'year':'2008'},source)
  self.assertEqual(diagnosis['status'],'mismatch');self.assertIn('不能视为同一来源',diagnosis['reason'])
  result=match_member({'author':'Nock et al.','year':'2008'},[source])
  self.assertEqual(result['status'],'unmatched')
 def test_confirmed_year_error_requires_explicit_reliable_basis(self):
  source=self.source('Smith',year='2024');source['year_verification']={'status':'confirmed','applicable_year':'2024','basis':'Crossref 正式卷期'}
  result=match_member({'author':'Smith','year':'2022'},[source])
  self.assertEqual(result['status'],'needs_assignment');self.assertEqual(result['year_diagnosis']['status'],'confirmed_error')
 def test_accent_normalization_preserves_metadata_evidence_check(self):
  text='Penadés 2023 Attention Study'
  r=verify_metadata(dict(title='Attention Study',authors='Penades',year='2023',quote=text),text)
  self.assertTrue(r['metadata_verified'])
 def test_leading_filename_author_and_year_allow_unique_provisional_match(self):
  source=dict(id='one',filename='Swisher 2026（NSSI功能导向）.pdf',authors='bad extraction',year='',title='Why compulsions persist',metadata_verified=False,attachment_status='available')
  result=match_member(dict(author='Swisher & Newman',year='2026'),[source])
  self.assertEqual(result['status'],'matched');self.assertEqual(result['identity_basis'],'filename_provisional')
 def test_pdf_year_can_correct_a_mislabeled_filename_year(self):
  source=dict(id='one',filename='Yang 2017（NSSI性别反转）.pdf',authors='Chinese adolescents',year='2018',title='A reversed gender pattern',metadata_verified=False,attachment_status='available')
  result=match_member(dict(author='Yang & Feldman',year='2018'),[source])
  self.assertEqual(result['status'],'matched');self.assertIn('PDF 解析年份',result['reason'])
 def test_filename_hint_stays_conservative_for_wrong_year_nonleading_or_multiple(self):
  base=dict(authors='bad extraction',year='',title='Study',metadata_verified=False,attachment_status='available')
  wrong=dict(id='wrong',filename='Swisher 2025.pdf',**base)
  nonleading=dict(id='nonleading',filename='Notes about Swisher 2026.pdf',**base)
  self.assertEqual(match_member(dict(author='Swisher',year='2026'),[wrong])['status'],'unmatched')
  self.assertEqual(match_member(dict(author='Swisher',year='2026'),[nonleading])['status'],'unmatched')
  one=dict(id='one',filename='Swisher 2026 one.pdf',**base);two=dict(id='two',filename='Swisher 2026 two.pdf',**base)
  self.assertEqual(match_member(dict(author='Swisher',year='2026'),[one,two])['status'],'needs_assignment')
 def test_unreadable_filename_hint_is_not_matched(self):
  source=dict(id='one',filename='Fawcett 2020.pdf',authors='',year='',title='',metadata_verified=False,attachment_status='unreadable')
  self.assertEqual(match_member(dict(author='Fawcett',year='2020'),[source])['status'],'unmatched')
 def test_one_verified_candidate_wins_over_an_unconfirmed_duplicate(self):
  verified=dict(id='verified',filename='Swisher and Newman 2026.pdf',authors='Swisher, Valerie',year='2026',title='Study',metadata_verified=True,attachment_status='available')
  duplicate=dict(id='new',filename='Swisher 2026 replacement.pdf',authors='bad extraction',year='2026',title='Study',metadata_verified=False,attachment_status='available')
  result=match_member(dict(author='Swisher',year='2026'),[verified,duplicate])
  self.assertEqual(result['status'],'matched');self.assertEqual(result['source_id'],'verified')
