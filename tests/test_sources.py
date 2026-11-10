import base64,unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from pypdf import PdfWriter
from app.sources import AssetStore
class SourceTests(unittest.TestCase):
 def test_pdf_confirm_and_bib(self):
  with TemporaryDirectory() as d:
   p=Path(d)/'sample.pdf';w=PdfWriter();w.add_blank_page(width=595,height=842);w.add_metadata({'/Title':'A study','/Author':'Smith'});w.write(p)
   store=AssetStore(Path(d)/'assets');s=store.upload('sample.pdf',base64.b64encode(p.read_bytes()).decode())
   self.assertEqual(s['title'],'A study');self.assertFalse(s['metadata_verified'])
   s=store.confirm(s['id'],{'year':'2023','online_year':'2022','publication_year':'2023','year_basis':'正式卷期记录'});self.assertTrue(s['metadata_verified']);self.assertEqual(s['year_verification']['applicable_year'],'2023')
   rows=store.bibliography('@article{a,title={A study},author={Smith, Jane},year={2023}}',[s['id']]);self.assertEqual(rows[0]['attachment_status'],'available')
   rows=store.bibliography('@article{b,title={Other},author={Doe},year={2021}}',[]);self.assertEqual(rows[0]['attachment_status'],'missing')
   with self.assertRaises(ValueError):store.upload('fake.pdf',base64.b64encode(b'fake').decode())
   with self.assertRaises(ValueError):store.get('../bad')
