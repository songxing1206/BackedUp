import sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from app.platform_support import startup_lock,open_directory
from app.model_settings import SettingsStore

class WindowsSupportTests(unittest.TestCase):
 def test_windows_lock_releases_same_byte_on_exception(self):
  native=types.SimpleNamespace(LK_NBLCK=1,LK_UNLCK=2,locking=Mock())
  with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'msvcrt':native}),patch('sys.platform','win32'):
   with self.assertRaisesRegex(ValueError,'fixture'):
    with startup_lock(Path(d)/'startup.lock'):raise ValueError('fixture')
   self.assertEqual([c.args[1:] for c in native.locking.call_args_list],[(1,1),(2,1)])
 def test_windows_lock_contention_has_timeout(self):
  native=types.SimpleNamespace(LK_NBLCK=1,LK_UNLCK=2,locking=Mock(side_effect=OSError('busy')))
  with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'msvcrt':native}),patch('sys.platform','win32'):
   with self.assertRaisesRegex(RuntimeError,'启动流程'): 
    with startup_lock(Path(d)/'startup.lock',timeout=0):pass
 def test_explorer_receives_literal_unicode_path(self):
  with patch('sys.platform','win32'),patch('os.startfile',create=True) as start:
   open_directory(Path('用户 资料'))
   start.assert_called_once_with('用户 资料')
 def test_windows_cli_is_explicitly_unavailable(self):
  with tempfile.TemporaryDirectory() as d,patch('sys.platform','win32'):
   with self.assertRaisesRegex(ValueError,'仅支持模型API'):SettingsStore(Path(d)/'model.json').save({'provider':'codex','model':'fixture'})
