import unittest,tempfile,threading,json,base64,time
from pathlib import Path
from pdf_fixture import make_pdf
from app.sources import AssetStore
from app.tasks import TaskStore
from app.evidence import EvidenceService
from app.automatic_review import ReviewQueue,chunks,verify_metadata

class AutoTests(unittest.TestCase):
 def test_cached_pdf_still_checks_current_limits_before_api(self):
  from unittest.mock import patch
  calls=[]
  class Fake:
   def call(_,prompt,event):calls.append(prompt);raise AssertionError('must not call API')
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  try:
   q._index(self.s)
   with patch('app.pdf_index.MAX_CHARACTERS',5):
    job=q.start('Claim (Smith, 2023).',[self.s['id']]);q.wait(job['id'],5)
   self.assertEqual(q.get(job['id'])['status'],'failed');self.assertEqual(calls,[])
  finally:q.close()
 def test_late_pdf_limit_prevents_all_model_calls(self):
  from unittest.mock import patch
  from app.pdf_index import PDFLimitError
  calls=[]
  class Fake:
   def call(_,prompt,event):calls.append(prompt);raise AssertionError('API must not run')
  p=make_pdf(self.root/'second.pdf',pages=[[(50,730,'Another source')]])
  second=self.assets.upload('second.pdf',base64.b64encode(p.read_bytes()).decode())
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  original=q._index
  def check(s):
   if s['id']==second['id']:raise PDFLimitError('PDF exceeds character protection')
   return original(s)
  try:
   with patch.object(q,'_index',side_effect=check):
    job=q.start('Claim (Smith, 2023).',[self.s['id'],second['id']]);q.wait(job['id'],5)
   self.assertEqual(q.get(job['id'])['status'],'failed');self.assertEqual(calls,[])
  finally:q.close()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.assets=AssetStore(self.root/'assets');self.tasks=TaskStore(self.root/'tasks');self.evidence=EvidenceService(self.tasks,self.assets,self.root/'evidence')
  p=make_pdf(self.root/'p.pdf',pages=[[(50,730,'Smith 2023 Attention Study'),(50,710,'Training improved recall in adults.')]])
  self.s=self.assets.upload('Smith.pdf',base64.b64encode(p.read_bytes()).decode())
 def tearDown(self):self.temp.cleanup()
 def test_metadata_requires_real_quote(self):
  row={'title':'Attention Study','authors':'Smith','year':'2023','quote':'Smith 2023 Attention Study'}
  self.assertTrue(verify_metadata(row,'Smith 2023 Attention Study')['metadata_verified'])
  with self.assertRaises(ValueError):verify_metadata({**row,'quote':'Invented title'},'Smith 2023 Attention Study')
  with self.assertRaises(ValueError):verify_metadata({**row,'authors':'Jones'},'Smith 2023 Attention Study')
 def test_chunk_coverage(self):
  blocks=[{'id':str(i),'text':'a'*20,'physical_page':i+1} for i in range(10)]
  parts=chunks(blocks,200);self.assertEqual([b['id'] for part in parts for b in part],[str(i) for i in range(10)])
 def test_dedup_upload(self):
  same=self.assets.upload('renamed.pdf',base64.b64encode(Path(self.s['path']).read_bytes()).decode());self.assertEqual(self.s['id'],same['id'])
 def test_full_automatic_verified_highlight(self):
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1])
    if data['phase']=='metadata':return {'title':'Attention Study','authors':'Smith','year':'2023','quote':'Smith 2023 Attention Study'}
    if data['phase']=='review':
     source=data['sources'][0];block=source['blocks'][1]
     return {'claims':[{'id':'P1','text':'Training helps recall','source_judgments':[{'source_id':source['id'],'status':'支持','reason':'明确结果','evidence':[{'source_id':source['id'],'pdf_sha256':source['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'原文支持'},'suggestion':None}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  j=q.start('Training helps recall (Smith, 2023).',[self.s['id'],self.s['id']]);q.wait(j['id'],5);j=q.get(j['id']);self.assertEqual(j['status'],'completed',j)
  t=self.tasks.get(j['task_id']);self.assertEqual(len(t['sources']),1);r=t['evidence_review']['locations'][0];self.assertEqual(r['combined']['status'],'支持');self.assertEqual(r['claims'][0]['source_judgments'][0]['evidence'][0]['validation'],'verified')
  self.assertEqual(j['execution_mode'],'agent');self.assertEqual(r['agent_result']['decisions'][0]['source_id'],self.s['id'])
  self.assertEqual(r['agent_result']['decisions'][0]['evidence_ids'][0],r['claims'][0]['source_judgments'][0]['evidence'][0]['id'])
  self.assertEqual(t['evaluation']['counts']['completed'],1);self.assertEqual(j['evaluation']['counts']['completed'],1)
  nodes={event['node'] for event in j['trace']};self.assertTrue({'citation_recognition','source_identity','pdf_index','evidence_retrieval','context_build','agent_review','evidence_validation','task_evaluation'}<=nodes)
  self.assertNotIn('Training helps recall',json.dumps(j['trace']))
  q.close()
 def test_missing_source_still_reports(self):
  class Fake:
   def call(_,p,e):return {'title':'Attention Study','authors':'Smith','year':'2023','quote':'Smith 2023 Attention Study'}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake());j=q.start('Missing (Jones, 2020).',[self.s['id']]);q.wait(j['id'],5)
  t=self.tasks.get(q.get(j['id'])['task_id']);self.assertEqual(t['summary']['unmatched'],1);self.assertEqual(q.get(j['id'])['status'],'partial');q.close()
 def test_unique_filename_identity_does_not_block_on_metadata_model(self):
  source=self.assets.get(self.s['id']);source.update(filename='Smith 2023 paper.pdf',authors='bad extraction',year='',metadata_verified=False,metadata_source='pdf_hints');self.assets.save(source);phases=[]
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1]);phases.append(data['phase'])
    if data['phase']=='metadata':raise AssertionError('provisional filename identity must not require a metadata request')
    src=data['sources'][0];block=src['blocks'][1]
    return {'claims':[{'id':'P1','text':'Training helps recall','source_judgments':[{'source_id':src['id'],'status':'支持','reason':'verified','evidence':[{'source_id':src['id'],'pdf_sha256':src['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'verified'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  try:
   job=q.start('Training helps recall (Smith, 2023).',[source['id']],review_mode='deep');q.wait(job['id'],5);saved=q.get(job['id'])
   self.assertEqual(saved['status'],'completed',saved);self.assertEqual(phases,['review'])
   member=self.tasks.get(saved['task_id'])['locations'][0]['members'][0];self.assertEqual(member['match']['identity_basis'],'filename_provisional')
  finally:q.close()
 def test_legacy_execution_mode_remains_available(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1]);source=data['sources'][0];block=source['blocks'][1]
    return {'claims':[{'id':'P1','text':'Training helps recall','source_judgments':[{'source_id':source['id'],'status':'支持','reason':'原文支持','evidence':[{'source_id':source['id'],'pdf_sha256':source['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'原文支持'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  try:
   j=q.start('Training helps recall (Smith, 2023).',[self.s['id']],review_mode='deep',execution_mode='legacy');q.wait(j['id'],5)
   job=q.get(j['id']);review=self.tasks.get(job['task_id'])['evidence_review']['locations'][0]
   self.assertEqual(job['status'],'completed');self.assertEqual(review['model']['execution_mode'],'legacy')
   self.assertIsNone(review.get('agent_result'))
  finally:q.close()

class LifecycleTests(AutoTests):
 def test_restart_marks_interrupted(self):
  jobs=self.root/'jobs';jobs.mkdir();jid='b'*32;(jobs/(jid+'.json')).write_text(json.dumps({'id':jid,'status':'running','stage':'old'}))
  q=ReviewQueue(self.tasks,self.assets,self.evidence,jobs,lambda:{})
  self.assertEqual(q.get(jid)['status'],'interrupted');q.close()
 def test_oversized_block_rejected_without_truncation(self):
  with self.assertRaises(ValueError):chunks([{'id':'large','text':'x'*100}],50)
 def test_partial_scope_not_definitive_negative(self):
  class Fake:
   def call(_,p,e):
    data=json.loads(p.split('\nDATA\n')[1]);sid=data['sources'][0]['id']
    return {'claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':sid,'status':'不支持','reason':'未找到','evidence':[]}]}],'combined':{'status':'不支持','reason':'未找到'}}
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  t=self.tasks.create('Claim (Smith, 2023).',[self.s]);pkg=self.evidence.prepare(t['id']);pkg['sources'][self.s['id']]['completeness']='partial'
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  jid='a'*32;q.events[jid]=threading.Event()
  row,_=q._review_location(jid,Fake(),pkg,t['locations'][0]);self.assertEqual(row['claims'][0]['source_judgments'][0]['status'],'无法判断');q.close()

class ValidationTests(AutoTests):
 def test_judgment_matrix_required(self):
  t=self.tasks.create('Claim (Smith, 2023).',[self.s]);q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  with self.assertRaises(ValueError):q._validate_row({'sources':{}},{'claims':[{'id':'P1','text':'Claim','source_judgments':[]}],'combined':{'status':'支持','reason':'yes'}},{'source'})
  q.close()
 def test_cancel_does_not_finish_late(self):
  entered=threading.Event()
  class Slow:
   def call(_,p,e):entered.set();e.wait(2);raise ValueError('cancel')
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{'provider':'fake','model':'x'},lambda s:Slow());j=q.start('Claim (Smith, 2023).',[self.s['id']]);entered.wait(1);q.cancel(j['id']);time.sleep(.05);self.assertEqual(q.get(j['id'])['status'],'cancelled');q.close()

class SuggestionTests(AutoTests):
 def test_failed_suggestion_recheck_keeps_original_result(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  t=self.tasks.create('Claim (Smith, 2023).',[self.s]);pkg=self.evidence.prepare(t['id'])
  class Fake:
   n=0
   def call(_,p,event):
    _.n+=1
    if _.n>1:raise ValueError('Suggestion check failed')
    i=pkg['sources'][self.s['id']];b=i['pages'][0]['blocks'][1]
    return {'claims':[{'id':'P1','text':'Claim','source_judgments':[{'source_id':self.s['id'],'status':'部分支持','reason':'limited','evidence':[{'source_id':self.s['id'],'pdf_sha256':i['sha256'],'block_id':b['id'],'quote':b['text'],'role':'限制'}]}]}],'combined':{'status':'部分支持','reason':'limited'},'suggestion':{'text':'Better claim (Smith, 2023).'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  jid='a'*32;q.events[jid]=threading.Event()
  row,_=q._review_location(jid,Fake(),pkg,t['locations'][0]);self.assertEqual(row['combined']['status'],'部分支持');self.assertFalse(row['suggestion']['verified']);q.close()

class RecoveryTests(AutoTests):
 def test_invalid_merge_evidence_falls_back_to_validated_chunk(self):
  from app.automatic_review import restore_validated_chunk_judgments
  sid='source';valid={'source_id':sid,'pdf_sha256':'hash','block_id':'block','quote':'exact source text','role':'支持'}
  candidate={'claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':sid,'status':'部分支持','reason':'only part is covered','evidence':[valid]}]}],'combined':{'status':'部分支持'}}
  row={'claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':sid,'status':'无法判断','reason':'invalid merge quote','evidence':[],'verification_error':'content_unverified','invalid_evidence':[{'quote':'paraphrase'}]}]}],'combined':{'status':'无法判断'}}
  restored=restore_validated_chunk_judgments(row,[candidate],{sid})
  judgment=restored['claims'][0]['source_judgments'][0]
  self.assertEqual(judgment['status'],'部分支持');self.assertEqual(judgment['evidence'][0]['quote'],'exact source text')
  self.assertTrue(judgment['technical_note']);self.assertNotIn('合并摘录',judgment['reason'])
  self.assertEqual(restored['combined']['status'],'部分支持');self.assertEqual(judgment['recovered_from'],'validated_chunk_fallback')
  row['claims'][0]['source_judgments'][0]={'source_id':sid,'status':'无法判断','reason':'merge incomplete','evidence':[]}
  candidate['claims'][0]['source_judgments'][0]['status']='支持'
  restored=restore_validated_chunk_judgments(row,[candidate],{sid})
  self.assertEqual(restored['claims'][0]['source_judgments'][0]['status'],'支持')
  row['claims'][0]['source_judgments'][0]={'source_id':sid,'status':'无法判断','evidence':[]}
  candidate['claims'][0]['text']='different claim'
  restored=restore_validated_chunk_judgments(row,[candidate],{sid})
  self.assertEqual(restored['claims'][0]['source_judgments'][0]['status'],'无法判断')
 def test_unverified_quote_repaired_without_guessing_position(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  t=self.tasks.create('Claim (Smith, 2023).',[self.s]);pkg=self.evidence.prepare(t['id']);sid=self.s['id'];index=pkg['sources'][sid];b=index['pages'][0]['blocks'][1]
  class Fake:
   calls=0
   def call(_,prompt,event):
    _.calls+=1
    quote='fabricated excerpt' if _.calls==1 else b['text']
    return {'claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':sid,'status':'支持','reason':'original','evidence':[{'source_id':sid,'pdf_sha256':index['sha256'],'block_id':b['id'],'quote':quote,'role':'支持'}]}]}],'combined':{'status':'支持','reason':'original'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  jid='a'*32;q.events[jid]=threading.Event();client=Fake()
  row=q._validated_call(jid,client,'review',{'phase':'review'},pkg,{sid})
  self.assertEqual(client.calls,2)
  e=row['claims'][0]['source_judgments'][0]['evidence'][0]
  self.assertEqual(self.evidence.verify_evidence(pkg,sid,e)['quote'],b['text']);q.close()
 def test_invalid_repair_still_rejected(self):
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  jid='a'*32;q.events[jid]=threading.Event()
  class Fake:
   calls=0
   def call(_,prompt,event):_.calls+=1;return {'claims':[]}
  client=Fake()
  with self.assertRaisesRegex(ValueError,'缺少子观点'):q._validated_call(jid,client,'review',{}, {'sources':{}},set())
  self.assertEqual(client.calls,2);q.close()

class BoundedRepairTests(AutoTests):
 def test_large_sources_merge_repair_stays_bounded(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  task=self.tasks.create('Training helps recall (Smith, 2023).',[self.s]);pkg=self.evidence.prepare(task['id']);sid=self.s['id'];block=pkg['sources'][sid]['pages'][0]['blocks'][1]
  pkg['sources'][sid]['pages'][0]['blocks'].extend([{**block,'id':'unused-'+str(i),'text':'Additional source material. '*8} for i in range(1800)])
  calls=[];merge_attempts=[];repairs=[]
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1]);calls.append(len(json.dumps(data,ensure_ascii=False)))
    assert calls[-1]<=81000
    if data['phase']=='merge':merge_attempts.append(data)
    if data['phase']=='repair':repairs.append(data)
    quote='not in PDF' if data['phase']=='merge' and len(merge_attempts)==1 else block['text']
    return {'claims':[{'id':'P1','text':'Training helps recall','source_judgments':[{'source_id':sid,'status':'支持','reason':'原文结果','evidence':[{'source_id':sid,'pdf_sha256':pkg['sources'][sid]['sha256'],'block_id':block['id'],'quote':quote,'role':'支持'}]}]}],'combined':{'status':'支持','reason':'原文结果'},'suggestion':None}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  try:
   jid='d'*32;q.events[jid]=threading.Event();row,_=q._review_location(jid,Fake(),pkg,task['locations'][0]);self.assertEqual(row['combined']['status'],'支持');self.assertGreater(len(calls),3);self.assertEqual(len(merge_attempts),1);self.assertEqual(len(repairs),1);self.assertNotIn('sources',repairs[-1]);self.assertNotIn('invalid_result',repairs[-1])
  finally:q.close()

class SupplementTests(unittest.TestCase):
 setUp=AutoTests.setUp
 tearDown=AutoTests.tearDown
 def test_supplement_only_checks_selected_location(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  text='First claim (Smith, 2023).\n\nSecond claim (Smith, 2023).'
  task=self.tasks.create(text,[self.s]);calls=[]
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1]);calls.append(data['sentence']);source=data['sources'][0]
    return {'claims':[{'id':'P1','text':data['sentence'],'source_judgments':[{'source_id':source['id'],'status':'不支持','reason':'原文只报告其他结果','evidence':[]}]}],'combined':{'status':'不支持','reason':'其他结果'}}
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda s:Fake())
  try:
   selected=task['locations'][1]['id'];job=q.start(text,[self.s['id']],task['id'],[selected],review_mode='deep');q.wait(job['id'],5)
   saved=self.tasks.get(task['id']);reviews={r['location_id']:r for r in saved['evidence_review']['locations']}
   self.assertEqual(q.get(job['id'])['total'],1);self.assertEqual(len(calls),1)
   self.assertEqual(reviews[selected]['combined']['status'],'不支持')
   self.assertEqual(reviews[task['locations'][0]['id']]['state'],'pending')
  finally:q.close()
