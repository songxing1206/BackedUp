import base64,json,unittest
import test_automatic_review as fixtures
from pdf_fixture import make_pdf
from app.automatic_review import ReviewQueue
from app.member_review import reusable_sources,merge_members

class MemberRetryTests(unittest.TestCase):
 setUp=fixtures.AutoTests.setUp
 tearDown=fixtures.AutoTests.tearDown
 def test_retry_only_sends_newly_available_source(self):
  self.run_retry(False)
 def test_failed_pending_source_keeps_completed_source(self):
  self.run_retry(True)
 def run_retry(self,fail):
  first=self.assets.confirm(self.s['id'],dict(title='Attention Study',authors='Smith',year='2023'))
  calls=[]
  class Fake:
   def call(_,prompt,event):
    d=json.loads(prompt.split('\nDATA\n')[1]);calls.append(d)
    if fail and len(calls)>1:raise ValueError('无法连接模型服务')
    s=d['sources'][0];b=next(b for b in s['blocks'] if 'Training' in b['text'])
    claim=d.get('fixed_claims',[dict(id='P1',text='Training improved recall')])[0]
    return dict(claims=[{**claim,'source_judgments':[dict(source_id=s['id'],status='支持',reason='verified',evidence=[dict(source_id=s['id'],pdf_sha256=s['sha256'],block_id=b['id'],quote=b['text'],role='支持')])]}],combined=dict(status='支持',reason='verified'))
  q=ReviewQueue(self.tasks,self.assets,self.evidence,self.root/'jobs',lambda:dict(provider='fake',model='test'),lambda _:Fake())
  try:
   j=q.start('Training improved recall (Smith, 2023; Jones, 2023).',[first['id']]);q.wait(j['id']);tid=q.get(j['id'])['task_id']
   self.assertEqual(len(calls),1)
   p=make_pdf(self.root/'jones.pdf',pages=[[(50,730,'Jones 2023 Other Study'),(50,710,'Training improved recall in adults.')]])
   second=self.assets.upload('Jones.pdf',base64.b64encode(p.read_bytes()).decode());second=self.assets.confirm(second['id'],dict(title='Other Study',authors='Jones',year='2023'))
   j=q.start('Training improved recall (Smith, 2023; Jones, 2023).',[first['id'],second['id']],tid);q.wait(j['id'])
   self.assertEqual(len(calls),2);self.assertEqual([s['id'] for s in calls[1]['sources']],[second['id']]);self.assertNotIn('fixed_claims',calls[1])
   reviews={r['location_id']:r for r in self.tasks.get(tid)['evidence_review']['locations']}
   first_judgments=reviews['C001']['claims'][0]['source_judgments']
   self.assertEqual(next(j for j in first_judgments if j['source_id']==first['id'])['status'],'支持')
   self.assertEqual(reviews['C001']['combined']['status'],'支持')
   self.assertEqual(reviews['C002']['combined']['status'],'无法判断' if fail else '支持')
  finally:q.close()
 def test_changed_dependency_and_unverified_evidence_prevent_reuse(self):
  previous={'member_keys':{'one':'key'},'claims':[{'source_judgments':[dict(source_id='one',status='支持',evidence=[{}])]}]}
  self.assertEqual(reusable_sources(previous,{'one':'changed'},lambda *_:None),set())
  def invalid(*_):raise ValueError('invalid quote')
  self.assertEqual(reusable_sources(previous,{'one':'key'},invalid),set())
 def test_altered_claim_text_is_not_accepted(self):
  old=dict(location_id='C001',claims=[dict(id='P1',text='original',source_judgments=[dict(source_id='one',status='支持')])])
  new=dict(claims=[dict(id='P1',text='changed',source_judgments=[dict(source_id='two',status='支持')])])
  merged=merge_members(old,new,{'one'},{'one','two'})
  self.assertEqual(merged['claims'][0]['text'],'original');self.assertEqual(merged['combined']['status'],'无法判断')
