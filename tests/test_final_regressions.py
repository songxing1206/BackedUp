from test_automatic_review import AutoTests
from app.automatic_review import ReviewQueue
import json,threading

class FinalRegressions(AutoTests):
 def client(self,calls):
  owner=self
  class Fake:
   def call(_,prompt,event):
    d=json.loads(prompt.split('\nDATA\n')[1]);calls.append(d['phase'])
    if d['phase']=='metadata':return {'title':'Attention Study','authors':'Smith','year':'2023','quote':'Smith 2023 Attention Study'}
    s=d['sources'][0];b=s['blocks'][1]
    return {'claims':[{'id':'P1','text':'Claim','source_judgments':[{'source_id':s['id'],'status':'支持','reason':'result','evidence':[{'source_id':s['id'],'pdf_sha256':s['sha256'],'block_id':b['id'],'quote':b['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'result'},'suggestion':{'text':'Better claim (Smith, 2023; Jones, 2020).'} if 'Jones' in d['sentence'] else None}
  return Fake()
 def test_endpoint_change_invalidates_cache_and_retry(self):
  cfg={'provider':'fake','model':'same','base_url':'https://a.example'};calls=[]
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:cfg.copy(),lambda s:self.client(calls))
  try:
   a=q.start('Training improved recall (Smith, 2023).',[self.s['id']]);q.wait(a['id']);a=q.get(a['id']);calls.clear();cfg['base_url']='https://b.example'
   b=q.start('Training improved recall (Smith, 2023).',[self.s['id']],a['task_id']);q.wait(b['id']);self.assertIn('review',calls);calls.clear();cfg['base_url']='https://c.example'
   c=q.start('Training improved recall (Smith, 2023).',[self.s['id']]);q.wait(c['id']);self.assertIn('review',calls)
  finally:q.close()
 def test_missing_citation_cannot_verify_suggestion(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  t=self.tasks.create('Claim (Smith, 2023; Jones, 2020).',[self.s]);pkg=self.evidence.prepare(t['id']);q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{})
  try:
   jid='c'*32;q.events[jid]=threading.Event();row,_=q._review_location(jid,self.client([]),pkg,t['locations'][0]);self.assertFalse(row['suggestion']['verified'])
  finally:q.close()
 def test_zero_citations_rejected_before_model_calls(self):
  calls=[];q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:{'provider':'fake','model':'x'},lambda s:self.client(calls))
  try:
   with self.assertRaisesRegex(ValueError,'未识别'):q.start('No references in this input.',[self.s['id']])
   self.assertEqual(calls,[])
  finally:q.close()
