import copy,unittest,unittest.mock
from pathlib import Path
from tempfile import TemporaryDirectory
from pdf_fixture import make_pdf
from app.tasks import TaskStore
from app.sources import AssetStore
from app.evidence import EvidenceService
class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory();self.root=Path(self.temp.name);self.tasks=TaskStore(self.root/'tasks',split_grouped=False);self.assets=AssetStore(self.root/'assets');self.s=[]
  for author,year,rows in [('Smith','2023',[[ (50,730,'Attention training improved recall.'),(50,710,'Only healthy adults were studied.')],[(50,730,'Attention training improved recall.')]]),('Doe','2021',[[(50,730,'Practice improved accuracy.')]])]:
   import uuid
   sid=uuid.uuid4().hex;p=make_pdf(self.root/(sid+'.pdf'),pages=rows);s=dict(id=sid,title=author,authors=author,year=year,path=str(p),metadata_verified=True,attachment_status='available');self.assets.save(s);self.s.append(s)
  self.t=self.tasks.create('Training improves recall and practice improves accuracy (Smith, 2023; Doe, 2021).',[*self.s]);self.service=EvidenceService(self.tasks,self.assets,self.root/'evidence');self.package=self.service.prepare(self.t['id'])
 def tearDown(self):self.temp.cleanup()
 def result(self):
  claims=[]
  for i,s in enumerate(self.s):
   index=self.package['sources'][s['id']];block=index['pages'][0]['blocks'][0]
   claims.append(dict(id=f'P{i+1}',text=['Training improves recall','Practice improves accuracy'][i],source_judgments=[dict(source_id=s['id'],status='支持',reason='对应结果',evidence=[dict(source_id=s['id'],pdf_sha256=index['sha256'],block_id=block['id'],start=0,end=len(block['text']),quote=block['text'],role='支持')])]))
  for c in claims:
   for other in self.s:
    if other['id']!=c['source_judgments'][0]['source_id']:c['source_judgments'].append(dict(source_id=other['id'],status='无法判断',reason='该材料没有此子观点的证据',evidence=[]))
  return dict(reading={s['id']:list(range(1,self.package['sources'][s['id']]['total_pages']+1)) for s in self.s},task_id=self.t['id'],package_id=self.package['package_id'],model={'name':'test model','version':'unknown'},locations=[dict(location_id=self.t['locations'][0]['id'],claims=claims,combined=dict(status='支持',reason='两篇分别支持子观点'))])
 def test_full_and_multi_source(self):
  r=self.service.import_result(self.t['id'],self.result());review=r['evidence_review']['locations'][0]
  self.assertEqual(len(review['claims']),2);self.assertEqual(review['combined']['status'],'支持');self.assertTrue(all(e['validation']=='verified' for c in review['claims'] for j in c['source_judgments'] for e in j['evidence']))
 def test_shared_package_export_preserves_geometry_and_validation(self):
  exported=self.service.export_json(self.t['id'],self.package)
  sid=self.s[0]['id'];self.assertNotIn('chars',exported['sources'][sid]['pages'][0])
  self.assertTrue(self.package['sources'][sid]['pages'][0]['chars'])
  with unittest.mock.patch.object(self.service,'load',side_effect=AssertionError('duplicate disk load')):
   self.service.import_result(self.t['id'],self.result(),self.package)
  make_pdf(Path(self.s[0]['path']),pages=[[(50,730,'Changed PDF.')]])
  with self.assertRaisesRegex(ValueError,'变化'):self.service.import_result(self.t['id'],self.result(),self.package)
 def test_tampering_atomic(self):
  for field,value in [('source_id','foreign'),('pdf_sha256','old'),('quote','Invented words')]:
   with self.subTest(field=field):
    data=self.result();data['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0][field]=value
    with self.assertRaises(ValueError):self.service.import_result(self.t['id'],data)
    self.assertNotIn('evidence_review',self.tasks.get(self.t['id']))
 def test_duplicate_without_range(self):
  data=self.result();e=data['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0];e.pop('block_id');e.pop('start');e.pop('end')
  task=self.service.import_result(self.t['id'],data)
  result=task['evidence_review']['locations'][0]['claims'][0]['source_judgments'][0]
  self.assertEqual(result['status'],'支持');self.assertEqual(result['evidence'][0]['location_state'],'unmapped');self.assertEqual(result['evidence'][0]['regions'],[])
 def test_verified_text_with_coordinate_failure_keeps_semantic_status(self):
  from unittest.mock import patch
  data=self.result()
  with patch('app.evidence.sentence_evidence',side_effect=ValueError('选定范围没有可定位字符')):
   task=self.service.import_result(self.t['id'],data)
  review=task['evidence_review']['locations'][0]
  self.assertEqual(review['combined']['status'],'支持')
  self.assertEqual(review['display_result']['color'],'green')
  self.assertEqual(review['status_detail']['content_validation_status'],'verified')
  self.assertEqual(review['status_detail']['localization_status'],'unmapped')
  evidence=review['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(evidence['validation'],'text_verified');self.assertEqual(evidence['location_state'],'unmapped')
 def test_foreign_task_and_incomplete_results(self):
  data=self.result();data['task_id']='foreign'
  with self.assertRaises(ValueError):self.service.import_result(self.t['id'],data)
  data=self.result();data['locations']=[];r=self.service.import_result(self.t['id'],data);self.assertEqual(r['evidence_review']['state'],'partial')
 def test_pdf_changed(self):
  make_pdf(Path(self.s[0]['path']),pages=[[(50,730,'Updated source.')]])
  with self.assertRaisesRegex(ValueError,'变化|失效'):self.service.import_result(self.t['id'],self.result())
 def test_reassignment_invalidates_preserves(self):
  self.service.import_result(self.t['id'],self.result());r=self.tasks.assign(self.t['id'],'C001-R1',self.s[0]['id'])
  self.assertEqual(r['evidence_review']['locations'][0]['state'],'stale');self.assertTrue(r['evidence_history'])
 def test_missing_source_incomplete_combined(self):
  t=self.tasks.create('Training helps (Smith, 2023; Jones, 2020).',self.s);package=self.service.prepare(t['id']);data=self.result();data.update(task_id=t['id'],package_id=package['package_id']);data['locations'][0]['claims']=data['locations'][0]['claims'][:1];data['locations'][0]['claims'][0]['source_judgments']=data['locations'][0]['claims'][0]['source_judgments'][:1];data['reading']={self.s[0]['id']:[1,2]}
  r=self.service.import_result(t['id'],data);review=r['evidence_review']['locations'][0]
  self.assertEqual(review['combined']['status'],'无法判断')
  self.assertEqual(review['claims'][0]['source_judgments'][0]['status'],'支持');self.assertTrue(review['claims'][0]['source_judgments'][0]['evidence'])
 def test_cross_page_multiple_fragments(self):
  data=self.result();j=data['locations'][0]['claims'][0]['source_judgments'][0];e=copy.deepcopy(j['evidence'][0]);b=self.package['sources'][self.s[0]['id']]['pages'][1]['blocks'][0];e.update(block_id=b['id'],start=0,end=len(b['text']),quote=b['text']);j['evidence'].append(e)
  r=self.service.import_result(self.t['id'],data);evidence=r['evidence_review']['locations'][0]['claims'][0]['source_judgments'][0]['evidence'];self.assertEqual([e['regions'][0]['physical_page'] for e in evidence],[1,2])

class EvidenceEdgeTests(unittest.TestCase):
 setUp=EvidenceTests.setUp
 tearDown=EvidenceTests.tearDown
 result=EvidenceTests.result
 def test_normalized_unique_quote_without_offsets(self):
  data=self.result();e=data['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0];e.pop('start');e.pop('end');e['quote']='Attention   training improved recall.'
  r=self.service.import_result(self.t['id'],data);q=r['evidence_review']['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0];self.assertEqual(q['quote'],'Attention training improved recall.');self.assertEqual(q['normalization'],'whitespace_linebreak_hyphen')
 def test_failed_source_does_not_block_export(self):
  Path(self.s[1]['path']).unlink();p=self.service.prepare(self.t['id']);self.assertEqual(p['sources'][self.s[1]['id']]['completeness'],'failed');self.assertIn('Attention',self.service.export_markdown(self.t['id']))

class ReviewLifecycleTests(unittest.TestCase):
 setUp=EvidenceTests.setUp
 tearDown=EvidenceTests.tearDown
 result=EvidenceTests.result
 def test_assignment_before_first_review_invalidates_package(self):
  self.tasks.assign(self.t['id'],'C001-R1',self.s[1]['id'])
  with self.assertRaisesRegex(ValueError,'失效'):self.service.export_json(self.t['id'])
  with self.assertRaisesRegex(ValueError,'失效'):self.service.import_result(self.t['id'],self.result())
 def test_pdf_change_invalidates_judgment_without_excerpts(self):
  data=self.result()
  for c in data['locations'][0]['claims']:
   for j in c['source_judgments']:j.update(status='无法判断',reason='未找到足够证据',evidence=[])
  self.service.import_result(self.t['id'],data);make_pdf(Path(self.s[0]['path']),pages=[[(50,730,'Replacement source.')]])
  self.service.prepare(self.t['id']);t=self.tasks.get(self.t['id']);self.assertEqual(t['evidence_review']['locations'][0]['state'],'stale');self.assertTrue(t['evidence_history'])
 def test_partial_repair_preserves_unaffected_completed_location(self):
  t=self.tasks.create('A (Smith, 2023; Doe, 2021). B (Doe, 2021).',self.s);p=self.service.prepare(t['id']);data=self.result();data.update(task_id=t['id'],package_id=p['package_id']);second=dict(location_id='C002',claims=[copy.deepcopy(data['locations'][0]['claims'][1])],combined={'status':'支持','reason':'来源明确'})
  second['claims'][0]['source_judgments']=[j for j in second['claims'][0]['source_judgments'] if j['source_id']==self.s[1]['id']];data['locations'].append(second);done=self.service.import_result(t['id'],data);old=copy.deepcopy(done['evidence_review']['locations'][1])
  self.tasks.assign(t['id'],'C001-R1',self.s[0]['id']);p=self.service.prepare(t['id']);data.update(package_id=p['package_id']);data['locations']=data['locations'][:1];done=self.service.import_result(t['id'],data);self.assertEqual(done['evidence_review']['locations'][1],old)
  data['locations']=[];done=self.service.import_result(t['id'],data);self.assertEqual(done['evidence_review']['locations'][1],old)

 def test_comma_line_wrap_expands_same_sentence(self):
  from app.pdf_index import parse_pdf
  sid=self.s[0]['id'];path=make_pdf(self.root/'wrapped.pdf',pages=[[(50,730,'NSSI is defined as direct,'),(50,710,'repetitive injury without suicidal intent.'),(50,690,'Another sentence follows.')]])
  index=parse_pdf(path,sid);page=index['pages'][0];package={'sources':{sid:index}}
  results=[]
  for block in page['blocks'][:2]:
   results.append(self.service.verify_evidence(package,sid,dict(source_id=sid,pdf_sha256=index['sha256'],block_id=block['id'],quote=block['text'],role='支持')))
  self.assertEqual(results[0]['quote'],results[1]['quote'])
  self.assertIn('direct,',results[0]['quote']);self.assertIn('suicidal intent.',results[0]['quote'])
  self.assertNotIn('Another',results[0]['quote']);self.assertEqual(len(results[0]['regions']),2)

 def test_invalid_offsets_recovered_from_unique_verbatim_quote(self):
  e=self.result()['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0]
  e.update(start=-1,end=99999)
  checked=self.service.verify_evidence(self.package,e['source_id'],e)
  self.assertEqual(checked['location_state'],'mapped');self.assertEqual(checked['validation'],'verified')
 def test_ambiguous_quote_never_creates_preview(self):
  data=self.result();e=data['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0]
  for key in ['block_id','start','end']:e.pop(key)
  task=self.service.import_result(self.t['id'],data);checked=task['evidence_review']['locations'][0]['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(checked['validation'],'text_verified')
  with self.assertRaises(ValueError):self.service.preview(task['id'],checked['id'])

 def test_wrong_range_recovers_exact_quote(self):
  e=self.result()['locations'][0]['claims'][1]['source_judgments'][0]['evidence'][0]
  e.update(start=1,end=5)
  checked=self.service.verify_evidence(self.package,e['source_id'],e)
  self.assertEqual(checked['start'],0)
  self.assertEqual(checked['location_state'],'mapped')
 def test_wrong_block_recovers_without_guessing(self):
  e=self.result()['locations'][0]['claims'][1]['source_judgments'][0]['evidence'][0]
  e['block_id']='foreign'
  checked=self.service.verify_evidence(self.package,e['source_id'],e)
  self.assertNotEqual(checked['block_id'],'foreign')
  self.assertEqual(checked['location_state'],'mapped')

 def test_local_failure_preserves_other_source(self):
  from app.automatic_review import ReviewQueue
  q=ReviewQueue(self.tasks,self.assets,self.service,self.root/'jobs',lambda:{})
  row=self.result()['locations'][0]
  row['claims'][0]['source_judgments'][0]['evidence'][0]['quote']='Invented evidence'
  q._call=lambda *args:copy.deepcopy(row)
  try:
   checked=q._validated_call('a'*32,None,'review',{},self.package,{s['id'] for s in self.s})
   self.assertEqual(checked['combined']['status'],'无法判断')
   self.assertEqual(checked['claims'][0]['source_judgments'][0]['status'],'无法判断')
   self.assertEqual(checked['claims'][1]['source_judgments'][0]['status'],'支持')
   self.assertTrue(checked['claims'][1]['source_judgments'][0]['evidence'])
  finally:q.close()

 def test_invalid_excerpt_is_removed_but_other_verified_excerpt_survives(self):
  from app.automatic_review import ReviewQueue
  q=ReviewQueue(self.tasks,self.assets,self.service,self.root/'jobs',lambda:{})
  row=self.result()['locations'][0];judgment=row['claims'][0]['source_judgments'][0]
  bad=copy.deepcopy(judgment['evidence'][0]);bad['quote']='Invented evidence';judgment['evidence'].append(bad)
  q._call=lambda *args:copy.deepcopy(row)
  try:
   checked=q._validated_call('b'*32,None,'review',{},self.package,{s['id'] for s in self.s})
   kept=checked['claims'][0]['source_judgments'][0]
   self.assertEqual(kept['status'],'支持');self.assertEqual(len(kept['evidence']),1)
   self.assertEqual(kept['invalid_evidence'][0]['validation'],'failed')
  finally:q.close()

 def test_c004_interaction_boundary_maps_whole_contradiction_to_partial(self):
  from app.evidence import normalize_interaction_judgment,normalize_legacy_task
  claim='As thoughts became more intense or persisted longer, NSSI frequency, duration, and methods increased.'
  judgment={'status':'存在矛盾','reason':'duration was not an independent predictor'}
  evidence=[{'quote':'Higher thought intensity predicted increased NSSI frequency, longer NSSI durations and more methods to a greater extent in the context of longer thought durations.','validation':'verified','location_state':'mapped'}]
  adjusted=normalize_interaction_judgment(claim,judgment,evidence)
  self.assertEqual(adjusted['status'],'部分支持');self.assertEqual(adjusted['model_original_status'],'存在矛盾')
  task={'locations':[{'id':'C004','members':[{'match':{'status':'matched'}}]}],'evidence_review':{'locations':[{'location_id':'C004','state':'complete','claims':[{'text':claim,'source_judgments':[{**judgment,'evidence':evidence}]}],'combined':{'status':'存在矛盾','reason':'model'},'coverage':'full','source_fingerprints':{'s':'hash'},'agent_result':{'combined_status':'存在矛盾','decisions':[{'status':'存在矛盾'}]}}]}}
  normalized_task=normalize_legacy_task(task);review=normalized_task['evidence_review']['locations'][0]
  self.assertEqual(review['combined']['status'],'部分支持');self.assertEqual(review['agent_result']['decisions'][0]['status'],'部分支持');self.assertEqual(review['display_result']['color'],'yellow')

 def test_old_history_without_explicit_validation_stays_gray(self):
  from app.evidence import normalize_legacy_task
  task={'locations':[{'id':'C1','members':[{'match':{'status':'matched'}}]}],'evidence_review':{'locations':[{'location_id':'C1','state':'complete','claims':[{'text':'claim','source_judgments':[{'status':'支持','evidence':[{'quote':'legacy quote','location_state':'mapped'}]}]}],'combined':{'status':'支持','reason':'legacy'}}]}}
  result=normalize_legacy_task(task)['evidence_review']['locations'][0]
  self.assertEqual(result['status_detail']['content_validation_status'],'unverified');self.assertEqual(result['display_result']['color'],'gray')

 def test_old_history_explicit_aliases_are_normalized_but_evidence_guard_remains(self):
  from app.evidence import normalize_legacy_task
  evidence={'quote':'verified quote','validation':'text_verified','location_state':'unmapped'}
  task={'locations':[{'id':'C1','members':[{'match':{'status':'matched','source_id':'S1'}}]}],'evidence_review':{'locations':[{'location_id':'C1','state':'complete','claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':'S1','status':'partial','reason':'limited','evidence':[evidence]}]}],'combined':{'status':'partial','reason':'limited'},'coverage':'full','source_fingerprints':{'S1':'hash'}}]}}
  result=normalize_legacy_task(task)['evidence_review']['locations'][0]
  self.assertEqual(result['claims'][0]['source_judgments'][0]['status'],'部分支持');self.assertEqual(result['combined']['status'],'部分支持');self.assertEqual(result['display_result']['color'],'yellow')

 def test_c010_multi_source_missing_member_forces_gray_not_yellow(self):
  from app.evidence import build_display_result
  location={'members':[{'match':{'status':'matched'}},{'match':{'status':'unmatched'}}]}
  review={'state':'partial','combined':{'status':'部分支持'},'claims':[{'source_judgments':[{'status':'部分支持','evidence':[{'validation':'verified'}]}]}]}
  result=build_display_result(location,review)
  self.assertEqual(result['color'],'gray');self.assertEqual(result['label'],'来源尚未匹配');self.assertEqual(result['rule'],'source_identity_unmatched')

 def test_partial_support_with_documented_non_support_remains_yellow(self):
  from app.evidence import build_display_result
  location={'members':[{'match':{'status':'matched'}}]}
  review={'state':'complete','combined':{'status':'部分支持','reason':'one part supported; another absent'},'claims':[{'source_judgments':[{'status':'部分支持','evidence':[{'validation':'verified'}]},{'status':'不支持','reason':'full text does not report the mechanism','evidence':[]}]}]}
  result=build_display_result(location,review)
  self.assertEqual(result['color'],'yellow');self.assertEqual(result['rule'],'semantic_partial_support')

 def test_partial_support_with_unverified_affirmative_evidence_stays_gray(self):
  from app.evidence import build_display_result
  location={'members':[{'match':{'status':'matched'}}]}
  review={'state':'complete','combined':{'status':'部分支持'},'claims':[{'source_judgments':[{'status':'部分支持','evidence':[{'validation':'verified'}]},{'status':'支持','evidence':[]}]}]}
  result=build_display_result(location,review)
  self.assertEqual(result['color'],'gray');self.assertEqual(result['rule'],'evidence_validation_required')

 def test_gray_results_explain_distinct_failure_stage(self):
  from app.evidence import build_display_result
  pending=build_display_result({'members':[{'match':{'status':'matched'}}]},{'state':'pending','combined':{'status':'无法判断'}})
  ambiguous=build_display_result({'members':[{'author':'Smith','year':'2023','match':{'status':'needs_assignment'}}]},{'state':'partial','combined':{'status':'无法判断'}})
  missing=build_display_result({'members':[{'author':'Jones','year':'2020','match':{'status':'missing_attachment'}}]},{'state':'partial','combined':{'status':'无法判断'}})
  self.assertEqual((pending['label'],pending['rule']),('模型结果未保存','review_pending'))
  self.assertEqual((ambiguous['label'],ambiguous['rule']),('来源存在歧义','source_identity_ambiguous'))
  self.assertEqual((missing['label'],missing['rule']),('PDF 缺失','source_pdf_missing'))

 def test_author_match_with_pdf_year_mismatch_is_red(self):
  from app.evidence import build_display_result
  location={'members':[{'match':{'status':'unmatched','year_diagnosis':{'status':'mismatch','reason':'引用 2008，PDF 2009'}}}]}
  result=build_display_result(location,{'state':'partial','combined':{'status':'无法判断'}})
  self.assertEqual(result['color'],'red');self.assertEqual(result['rule'],'citation_pdf_year_mismatch')
