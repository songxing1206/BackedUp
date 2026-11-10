from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject

def make_pdf(path,pages=None,rotation=0,crop=None):
 writer=PdfWriter()
 for rows in pages or [[(50,730,'Repeated evidence.'),(50,710,'A second line.'),(330,730,'Right column evidence.')],[(50,730,'Repeated evidence.')],[]]:
  page=writer.add_blank_page(width=595,height=842)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  lines=[]
  for row in rows:
   x,y,text,*rest=row;size=rest[0] if rest else 12
   escaped=text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)');lines.append(f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET')
  stream=DecodedStreamObject();stream.set_data('\n'.join(lines).encode('latin1'));page[NameObject('/Contents')]=writer._add_object(stream)
  if rotation:page.rotate(rotation)
  if crop:page.cropbox.lower_left=crop[:2];page.cropbox.upper_right=crop[2:]
 writer.write(path);return Path(path)
