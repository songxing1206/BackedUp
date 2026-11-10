"""Read-only PDFium character index; rectangles use rendered-page coordinates."""
from contextlib import closing
import ctypes,hashlib,io,json,math,threading
from pathlib import Path
import pypdfium2 as pdfium
import pypdfium2.raw as raw

VERSION='pdfium-chars-3'
PDF_LOCK=threading.RLock() # PDFium is not thread safe.
MAX_PAGES=200
MAX_CHARACTERS=300000

class PDFLimitError(ValueError):pass

def fingerprint(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read_char(textpage,index):
 value=raw.FPDFText_GetUnicode(textpage,index)
 if 0xd800<=value<=0xdbff:
  following=raw.FPDFText_GetUnicode(textpage,index+1)
  if 0xdc00<=following<=0xdfff:return chr(0x10000+((value-0xd800)<<10)+following-0xdc00)
 return chr(value) if 0<value<=0x10ffff and not 0xd800<=value<=0xdfff else ''

def device_box(page,box,width,height):
 # PDFium applies CropBox, nonzero origins and intrinsic page rotation.
 points=[];factor=4
 for x,y in [(box[0],box[1]),(box[0],box[3]),(box[2],box[1]),(box[2],box[3])]:
  dx,dy=ctypes.c_int(),ctypes.c_int()
  if not raw.FPDF_PageToDevice(page,0,0,math.ceil(width*factor),math.ceil(height*factor),0,x,y,ctypes.byref(dx),ctypes.byref(dy)):raise ValueError('坐标转换失败')
  points.append((dx.value/factor,dy.value/factor))
 xs,ys=zip(*points);return [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]

def check_pdf_limits(path):
 """Count only; no coordinate index allocation and no cached-limit bypass."""
 with PDF_LOCK, pdfium.PdfDocument(path) as doc:
  if len(doc)>MAX_PAGES:raise PDFLimitError(f'单个PDF超过{MAX_PAGES}页，请拆分；未截断处理')
  count=0
  for n in range(len(doc)):
   with closing(doc[n]) as page, closing(page.get_textpage()) as textpage:
    count+=textpage.count_chars()
    if count>MAX_CHARACTERS:raise PDFLimitError(f'单个PDF超过{MAX_CHARACTERS:,}个字符，请拆分；未截断处理')
  return dict(pages=len(doc),characters=count)

def parse_pdf(path,source_id):
 path=Path(path);result=dict(source_id=source_id,sha256=fingerprint(path),parser_version=VERSION,pages=[],total_pages=0,read_pages=0,completeness='failed',warnings=[])
 with PDF_LOCK:
  try:
   with pdfium.PdfDocument(path) as doc:
    result['total_pages']=len(doc);character_count=0
    if len(doc)>MAX_PAGES:raise PDFLimitError(f'单个PDF超过{MAX_PAGES}页，请拆分；未截断处理')
    for n in range(len(doc)):
     page_record=dict(page_index=n,physical_page=n+1,state='failed',blocks=[],chars=[])
     try:
      with closing(doc[n]) as page:
       width,height=page.get_size();page_record.update(width=width,height=height,rotation=page.get_rotation(),cropbox=list(page.get_cropbox()),coordinate_origin='rendered_top_left')
       with closing(page.get_textpage()) as textpage:
        character_count+=textpage.count_chars()
        if character_count>MAX_CHARACTERS:raise PDFLimitError(f'单个PDF超过{MAX_CHARACTERS:,}个字符，请拆分；未截断处理')
        offset=0;line=[];blocks=[]
        def flush():
         if not line:return
         text=''.join(c['text'] for c in line)
         boxes=[c['box'] for c in line if c['box']]
         box=None
         if boxes:
          x=min(b[0] for b in boxes);y=min(b[1] for b in boxes);right=max(b[0]+b[2] for b in boxes);bottom=max(b[1]+b[3] for b in boxes);box=[x,y,right-x,bottom-y]
         if text.strip():blocks.append(dict(id=f"{result['sha256'][:16]}-p{n+1}-c{line[0]['index']}-{line[-1]['index']+1}",page_index=n,physical_page=n+1,page_width=width,text=text,start=line[0]['start'],end=line[-1]['end'],char_start=line[0]['index'],char_end=line[-1]['index']+1,box=box))
         line.clear()
        for i in range(textpage.count_chars()):
         text=read_char(textpage,i);box=None
         if text and not text.isspace():
          try:
           native=textpage.get_charbox(i);box=device_box(page,native,width,height)
           if box[2]<=0 or box[3]<=0:box=None
          except Exception:box=None
         char=dict(index=i,text=text,start=offset,end=offset+len(text),box=box);offset+=len(text);page_record['chars'].append(char)
         if text in ['\r','\n']:flush()
         elif text:line.append(char)
        flush();page_record['blocks']=blocks;page_record['text']=''.join(c['text'] for c in page_record['chars']);page_record['state']='read' if page_record['text'].strip() else 'no_text'
        if page_record['state']=='read':result['read_pages']+=1
        else:page_record['reason']='无可提取文字，未执行OCR'
     except PDFLimitError:raise
     except Exception as e:page_record['reason']=str(e)[:200]
     result['pages'].append(page_record)
    result['completeness']='complete' if result['read_pages']==result['total_pages'] and result['total_pages'] else 'partial' if result['read_pages'] else 'unreadable'
    from .document_schema import build_document
    result['document']=build_document(path,result,path.name)
  except PDFLimitError:raise
  except Exception as e:result['warnings'].append(str(e)[:200])
 return result

def render_page(path,page_index,scale=1.5):
 if not isinstance(page_index,int) or page_index<0 or not 0.25<=scale<=3:raise ValueError('无效页码或缩放')
 with PDF_LOCK,pdfium.PdfDocument(path) as doc:
  if page_index>=len(doc):raise ValueError('页码越界')
  with closing(doc[page_index]) as page:
   width,height=page.get_size()
   if width*height*scale*scale>24000000:raise ValueError('页面尺寸过大，无法安全渲染')
   with closing(page.render(scale=scale)) as bitmap:
    output=io.BytesIO();bitmap.to_pil().save(output,format='PNG');return output.getvalue()

def range_regions(page,block,start,end):
 if type(start)!=int or type(end)!=int or not 0<=start<end<=len(block['text']):raise ValueError('证据字符范围无效')
 absolute_start=block['start']+start;absolute_end=block['start']+end
 boxes=[c['box'] for c in page['chars'] if c['start']>=absolute_start and c['end']<=absolute_end and c['box'] and c['text'].strip()]
 if not boxes:raise ValueError('选定范围没有可定位字符')
 # One block is one original text line; never span unrelated line blocks.
 x=min(b[0] for b in boxes);y=min(b[1] for b in boxes);r=max(b[0]+b[2] for b in boxes);bottom=max(b[1]+b[3] for b in boxes)
 return [dict(page_index=page['page_index'],physical_page=page['physical_page'],box=[x,y,r-x,bottom-y],page_width=page['width'],page_height=page['height'])]
