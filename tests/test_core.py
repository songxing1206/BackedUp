import unittest
from app.citations import extract_locations
from app.matching import match_member
from app.tasks import TaskStore
from pathlib import Path
from tempfile import TemporaryDirectory

class CoreTests(unittest.TestCase):
 def test_group_and_repeat(self):
  r=extract_locations('Attention differs (Smith, 2023; Doe, 2021). Smith (2023) reported benefits.')
  self.assertEqual(len(r['locations']),3)
  self.assertTrue(all(len(loc['members'])==1 for loc in r['locations']))
  self.assertEqual(r['locations'][0]['citation_group_id'],r['locations'][1]['citation_group_id'])
  self.assertNotEqual(r['locations'][1]['id'],r['locations'][2]['id'])
 def test_link_offsets(self):
  text='Earlier text. Smith [(2023)](https://www.zotero.org/google-docs/?abc) found benefits.'
  r=extract_locations(text)['locations'][0]
  self.assertEqual(text[r['start']:r['end']],r['raw'])
  self.assertIn('Smith',r['raw']); self.assertIn('benefits',r['sentence'])
 def test_code_and_references(self):
  text='Claim (Smith, 2023).\n```text\nFake (Doe, 2021).\n```\n## References\nOther (Jones, 2022).'
  self.assertEqual(len(extract_locations(text)['locations']),1)
 def source(self,i,year=2023):
  return dict(id=i,authors='Smith, Jane',year=str(year),title=i,metadata_verified=True,attachment_status='available')
 def test_ambiguous(self):
  result=match_member(dict(author='Smith',year='2023'),[self.source('one'),self.source('two')])
  self.assertEqual(result['status'],'needs_assignment'); self.assertEqual(len(result['candidates']),2)
 def test_suffix(self):
  result=match_member(dict(author='Smith',year='2023a'),[self.source('one','2023a'),self.source('two','2023b')])
  self.assertEqual(result['source_id'],'one')
  result=match_member(dict(author='Smith',year='2023a'),[self.source('one')])
  self.assertEqual(result['status'],'needs_assignment')
 def test_missing_and_weak(self):
  source=self.source('one');source['attachment_status']='missing'
  self.assertEqual(match_member(dict(author='Smith',year=2023),[source])['status'],'missing_attachment')
  source['metadata_verified']=False
  self.assertEqual(match_member(dict(author='Smith',year=2023),[source])['status'],'needs_assignment')
 def test_assignment_and_isolation(self):
  with TemporaryDirectory() as d:
   store=TaskStore(Path(d))
   t=store.create('A (Smith, 2023). B (Doe, 2020).',[self.source('one'),self.source('two')])
   self.assertEqual(t['summary']['needs_assignment'],1)
   member=t['locations'][0]['members'][0]
   updated=store.assign(t['id'],member['id'],'one')
   self.assertEqual(updated['summary']['matched'],1)
   self.assertEqual(updated['locations'][1],t['locations'][1])
   with self.assertRaises(ValueError):store.assign(t['id'],member['id'],'foreign')
   with self.assertRaises(ValueError):store.get('../../outside')

if __name__=='__main__':unittest.main()
