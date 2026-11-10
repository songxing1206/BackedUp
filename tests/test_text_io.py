import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.text_io import read_text_compat, write_text_utf8


class TextIOTests(unittest.TestCase):
    def test_utf8_storage_preserves_characters_outside_windows_gbk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.json'
            write_text_utf8(path, '{"title":"中文 €"}')
            self.assertEqual(path.read_bytes().decode('utf-8'), '{"title":"中文 €"}')
            self.assertEqual(read_text_compat(path), '{"title":"中文 €"}')

    def test_old_windows_code_page_data_remains_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.json'
            path.write_bytes('{"title":"Résumé"}'.encode('cp1252'))
            with patch('app.text_io.locale.getencoding', return_value='cp1252'):
                self.assertEqual(read_text_compat(path), '{"title":"Résumé"}')


if __name__ == '__main__':
    unittest.main()
