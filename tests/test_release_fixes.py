import copy, io, tempfile, unittest, zipfile
from pathlib import Path
from app.automatic_review import restore_validated_chunk_judgments
from app.report_archive import write_report

class ReleaseFixTests(unittest.TestCase):
 def test_conflicting_chunk_judgments_are_not_promoted(self):
  evidence={'source_id':'S1','quote':'exact','role':'支持'}
  def row(status):
   return {'claims':[{'id':'P1','text':'claim','source_judgments':[{'source_id':'S1','status':status,'reason':'reason','evidence':[evidence] if status!='无法判断' else []}]}],'combined':{'status':status}}
  current=row('无法判断')
  restored=restore_validated_chunk_judgments(current,[row('支持'),row('存在矛盾')],{'S1'})
  self.assertEqual(restored['combined']['status'],'无法判断')
 def test_archive_duration_and_missing_duration(self):
  for duration,expected in [(12.5,'12.5 秒'),(None,'未记录')]:
   task={'schema_version':1,'sources':[],'locations':[],'evaluation':{'counts':{},'duration_seconds':duration}}
   with tempfile.TemporaryDirectory() as d:
    stream=io.BytesIO();write_report(task,Path(d),stream)
    with zipfile.ZipFile(stream) as z:page=z.read('report.html').decode()
   self.assertIn('本轮耗时 '+expected,page)
   self.assertIn('任务创建时间',page)

class UpgradeLaunchTests(unittest.TestCase):
 def test_old_service_is_not_silently_reused(self):
  import launcher
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d, patch('launcher.dependencies',return_value=[]), patch('launcher.data_dir',return_value=Path(d)/'data-v1'), patch('launcher.existing_service',return_value=(8787,{'version':'0.4.21-beta'})), patch('launcher.open_page') as opened:
   with self.assertRaisesRegex(RuntimeError,'不同版本'):launcher.launch(False)
   opened.assert_not_called()
