import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from pypdf import PdfReader,PdfWriter
from pypdf.generic import DecodedStreamObject,NameObject
from pdf_fixture import make_pdf
from app.pdf_index import parse_pdf,range_regions,render_page
from app.evidence import normalized,normalize_map
from app.report_archive import highlighted_page

class LocationSpecialTests(unittest.TestCase):
 def test_unicode_pdf_offsets_and_regions(self):
  with tempfile.TemporaryDirectory() as d:
   path=make_pdf(Path(d)/'base.pdf',pages=[[(70,720,'A B C.')]])
   reader=PdfReader(path);writer=PdfWriter();writer.append(reader);font=writer.pages[0]['/Resources']['/Font']['/F1'].get_object()
   cmap=DecodedStreamObject();cmap.set_data(b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapType 2 def 1 begincodespacerange <00> <FF> endcodespacerange 3 beginbfchar <41> <D83DDE00> <42> <03B2> <43> <5B57> endbfchar endcmap end end')
   font[NameObject('/ToUnicode')]=writer._add_object(cmap);path=Path(d)/'unicode.pdf';writer.write(path)
   page=parse_pdf(path,'fixture')['pages'][0]
   self.assertIn('😀',page['text']);self.assertIn('β',page['text']);self.assertIn('字',page['text'])
   for char in page['chars']:
    self.assertEqual(page['text'][char['start']:char['end']],char['text'])
   block=page['blocks'][0];regions=range_regions(page,block,0,len(block['text']));self.assertTrue(regions)
 def test_normalization_retains_original_indices(self):
  text='inter-\nvention\t improves\r\n recall.';clean,mapping=normalize_map(text)
  self.assertEqual(clean,normalized('intervention improves recall.'))
  self.assertTrue(all(0<=start<end<=len(text) for start,end in mapping));self.assertEqual(len(clean),len(mapping))
 def test_highlight_pixels_overlap_ink_for_rotated_crop(self):
  for angle in [0,90,180,270]:
   with self.subTest(angle=angle),tempfile.TemporaryDirectory() as d:
    path=make_pdf(Path(d)/'a.pdf',pages=[[(70,720,'Exact evidence.')]],rotation=angle,crop=(20,30,550,800));page=parse_pdf(path,'fixture')['pages'][0];block=page['blocks'][0]
    regions=range_regions(page,block,0,len(block['text']));image=Image.open(io.BytesIO(highlighted_page(path,regions))).convert('RGB')
    for region in regions:
     x,y,w,h=region['box'];sx=image.width/region['page_width'];sy=image.height/region['page_height'];crop=image.crop((int(x*sx),int(y*sy),int((x+w)*sx)+1,int((y+h)*sy)+1))
     pixels=crop.get_flattened_data() if hasattr(crop,'get_flattened_data') else crop.getdata()
     self.assertTrue(any(b>r and b>g and r<240 for r,g,b in pixels),'紫色高亮未覆盖坐标区域')
     self.assertTrue(any(max(pixel)<110 for pixel in pixels),'高亮区域没有对应文字墨迹')
