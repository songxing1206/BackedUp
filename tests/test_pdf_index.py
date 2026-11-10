import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pdf_fixture import make_pdf
from app.pdf_index import parse_pdf,render_page,read_char
class PdfIndexTests(unittest.TestCase):
 def test_pages_columns_repeat_blank(self):
  with TemporaryDirectory() as d:
   p=make_pdf(Path(d)/'a.pdf');r=parse_pdf(p,'one')
   self.assertEqual(r['total_pages'],3);self.assertEqual(r['pages'][2]['state'],'no_text');self.assertEqual(r['completeness'],'partial')
   texts=[b['text'] for page in r['pages'] for b in page['blocks']]
   self.assertEqual(sum('Repeated evidence.' in t for t in texts),2)
   ids=[b['id'] for page in r['pages'] for b in page['blocks']];self.assertEqual(len(ids),len(set(ids)))
   self.assertTrue(any('Right column' in t for t in texts));self.assertEqual(r['sha256'],parse_pdf(p,'other')['sha256'])
   self.assertTrue(render_page(p,0,1).startswith(b'\x89PNG'))
 def test_rotation_crop(self):
  for angle in [0,90,180,270]:
   with self.subTest(angle=angle),TemporaryDirectory() as d:
    p=make_pdf(Path(d)/'a.pdf',pages=[[(70,720,'Rotation check.')]],rotation=angle,crop=(20,30,550,800));r=parse_pdf(p,'one');page=r['pages'][0]
    self.assertEqual(page['rotation'],angle)
    for c in page['chars']:
     if c['text'].strip():
      x,y,w,h=c['box'];self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0);self.assertLessEqual(x+w,page['width']+1);self.assertLessEqual(y+h,page['height']+1)
 def test_unicode_uses_codepoints(self):
  with patch('app.pdf_index.raw.FPDFText_GetUnicode',return_value=0x1f600):self.assertEqual(read_char(None,0),'😀')
 def test_invalid(self):
  with TemporaryDirectory() as d:
   p=Path(d)/'bad.pdf';p.write_bytes(b'bad');r=parse_pdf(p,'one');self.assertEqual(r['completeness'],'failed')

class RenderAlignmentTests(unittest.TestCase):
 def test_glyph_boxes_cover_ink_for_rotated_crop(self):
  import io
  from PIL import Image
  for angle in [0,90,180,270]:
   with self.subTest(angle=angle),TemporaryDirectory() as d:
    p=make_pdf(Path(d)/'a.pdf',pages=[[(70,720,'Evidence')]],rotation=angle,crop=(20,30,550,800));page=parse_pdf(p,'one')['pages'][0];image=Image.open(io.BytesIO(render_page(p,0,2))).convert('L')
    for char in page['chars']:
     if not char['box']:continue
     x,y,w,h=char['box'];crop=image.crop((int(x*2)-2,int(y*2)-2,int((x+w)*2)+2,int((y+h)*2)+2));self.assertLess(crop.getextrema()[0],100,'glyph boundary missed actual rendered text')
