import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pdf_fixture import make_pdf
from app.pdf_index import parse_pdf,PDFLimitError,check_pdf_limits

class ResourceTests(unittest.TestCase):
 def test_preflight_counts_without_coordinate_allocation(self):
  with tempfile.TemporaryDirectory() as d:
   path=make_pdf(Path(d)/'count.pdf',pages=[[(50,730,'Fixture text.')]])
   result=check_pdf_limits(path)
   self.assertEqual(result['pages'],1);self.assertGreater(result['characters'],5)
   with patch('app.pdf_index.MAX_CHARACTERS',5),self.assertRaises(PDFLimitError):check_pdf_limits(path)
 def test_page_limit_rejects_whole_pdf(self):
  with tempfile.TemporaryDirectory() as d:
   path=make_pdf(Path(d)/'pages.pdf',pages=[[(50,730,'Fixture text.')]]*2)
   with patch('app.pdf_index.MAX_PAGES',1),self.assertRaisesRegex(PDFLimitError,'页'):parse_pdf(path,'fixture')
 def test_character_limit_rejects_instead_of_partial_success(self):
  with tempfile.TemporaryDirectory() as d:
   path=make_pdf(Path(d)/'chars.pdf',pages=[[(50,730,'Fixture text exceeds test limit.')]])
   with patch('app.pdf_index.MAX_CHARACTERS',5),self.assertRaisesRegex(PDFLimitError,'字符'):parse_pdf(path,'fixture')
