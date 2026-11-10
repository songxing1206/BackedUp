import json,threading,base64
from pdf_fixture import make_pdf
from test_automatic_review import AutoTests
from app.automatic_review import ReviewQueue

class RetrievalQueueTests(AutoTests):
 def queue(self,client):return ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda _:client)
 def test_suggestion_does_not_trigger_another_paid_review(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'});calls=[]
  class Fake:
   def call(_,prompt,event):
    data=json.loads(prompt.split('\nDATA\n')[1]);calls.append(data);source=data['sources'][0];block=source['blocks'][1]
    return {'claims':[{'id':'P1','text':'Training helps recall','source_judgments':[{'source_id':source['id'],'status':'支持','reason':'verified','evidence':[{'source_id':source['id'],'pdf_sha256':source['sha256'],'block_id':block['id'],'quote':block['text'],'role':'支持'}]}]}],'combined':{'status':'支持','reason':'verified'},'suggestion':{'text':'Improved (Smith, 2023).'}}
  q=self.queue(Fake())
  try:
   j=q.start('Training helps recall (Smith, 2023).',[self.s['id']]);q.wait(j['id']);saved=self.tasks.get(q.get(j['id'])['task_id'])['evidence_review']['locations'][0]
   self.assertEqual(len(calls),1);self.assertFalse(saved['suggestion']['verified']);self.assertEqual(saved['coverage'],'retrieved');self.assertEqual(saved['state'],'complete')
   self.assertIsInstance(saved['processing_seconds'],float);self.assertGreaterEqual(saved['processing_seconds'],0)
   job=q.get(j['id']);self.assertIn(timing:=next(iter(job['location_timings'])),job['location_timings']);self.assertGreaterEqual(job['location_timings'][timing],0)
  finally:q.close()
 def test_trial_does_not_request_metadata_for_unrelated_sources(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  class Fake:
   def call(_,p,e):raise AssertionError('No relevant unknown source should be sent')
  pdf=make_pdf(self.root/'unrelated.pdf',pages=[[(50,730,'Jones 2020 unrelated study')]])
  other=self.assets.upload('Jones.pdf',base64.b64encode(pdf.read_bytes()).decode());other=self.assets.confirm(other['id'],{'title':'Study','authors':'Jones','year':'2020'});other['metadata_verified']=False;self.assets.save(other)
  q=self.queue(Fake())
  try:
   text='Quantum mechanics (Smith, 2023).\n\nQuantum interactions (Smith, 2023).\n\nQuantum fields (Smith, 2023).\n\nUnrelated (Jones, 2020).'
   j=q.start(text,[self.s['id'],other['id']],location_limit=3);q.wait(j['id']);self.assertEqual(q.get(j['id'])['completed'],3);self.assertNotIn('budget_usage',q.get(j['id']))
  finally:q.close()
 def test_budget_pauses_before_model_request(self):
  self.s=self.assets.confirm(self.s['id'],{'title':'Attention Study','authors':'Smith','year':'2023'})
  class Fake:
   def call(_,p,e):raise AssertionError('Over budget must not call model')
  q=self.queue(Fake())
  try:
   j=q.start('Training recall '+('context '*500)+'(Smith, 2023).',[self.s['id']],token_budget=10000);q.wait(j['id']);self.assertEqual(q.get(j['id'])['status'],'paused')
  finally:q.close()
 def test_received_request_is_reused_after_queue_restart(self):
  calls=[]
  class Fake:
   def call(_,p,e):calls.append(1);return {'ok':True}
  q=self.queue(Fake());jid='c'*32;q.events[jid]=threading.Event()
  self.assertEqual(q._call(jid,Fake(),'JSON',{'phase':'review'}),{'ok':True});q.close()
  q=self.queue(Fake());q.events[jid]=threading.Event()
  try:self.assertEqual(q._call(jid,Fake(),'JSON',{'phase':'review'}),{'ok':True});self.assertEqual(calls,[1])
  finally:q.close()
