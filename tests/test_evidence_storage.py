import json,unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from app.evidence_storage import write_package,load_package,IndexedSources

class StreamingTests(unittest.TestCase):
 def test_large_batch_single_source_cache_and_legacy_compatibility(self):
  with TemporaryDirectory() as folder:
   path=Path(folder)/'package.json'
   header=dict(schema_version=1,task_id='test',package_id='package')
   rows=((str(i),dict(sha256=str(i),pages=[dict(chars=[{'text':'a'}]*150000)])) for i in range(3))
   package=write_package(path,header,rows);sources=package['sources']
   self.assertIsInstance(sources,IndexedSources)
   self.assertNotIn('pages',dict.values(sources).__iter__().__next__())
   for sid in sources:self.assertEqual(len(sources[sid]['pages'][0]['chars']),150000);self.assertEqual(sources.cached[0],sid)
   self.assertEqual(len(json.loads(path.read_text())['sources']),3)
   sources.clear_cache();self.assertIsNone(sources.cached)
   path.with_suffix('.offsets.json').unlink()
   self.assertEqual(len(load_package(path)['sources']['2']['pages'][0]['chars']),150000)
 def test_changed_package_never_uses_old_offsets(self):
  with TemporaryDirectory() as folder:
   path=Path(folder)/'package.json';package=write_package(path,{},[('one',dict(pages=[],sha256='original'))])
   path.write_text(json.dumps({'sources':{},'restored':True}))
   with self.assertRaises(ValueError):package['sources']['one']
   self.assertTrue(load_package(path)['restored'])
