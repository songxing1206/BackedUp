"""Recover malformed model-echoed hashes using supplied, verified provenance."""
import copy,re
from .evidence import normalized

def supplied_texts(package,source):
 """Original-order spans consisting only of contiguous supplied PDF blocks."""
 ids={b['id'] for b in source.get('blocks',[])};texts=[]
 index=package['sources'].get(source['id'])
 if not index:return texts
 for page in index['pages']:
  run=[]
  for block in page['blocks']:
   if block['id'] in ids:run.append(block)
   elif run:
    texts.append(page['text'][run[0]['start']:run[-1]['end']]);run=[]
  if run:texts.append(page['text'][run[0]['start']:run[-1]['end']])
 return texts

def bind_generated_identity(row,sources,allowed,verify,package):
 if not isinstance(row,dict) or not isinstance(row.get('claims'),list):return row
 result=copy.deepcopy(row)
 supplied={s['id']:s for s in sources if s.get('id') in allowed}
 for claim in result.get('claims',[]):
  if not isinstance(claim,dict):continue
  judgments=claim.get('source_judgments',[])
  if not isinstance(judgments,list):continue
  for judgment in judgments:
   if not isinstance(judgment,dict):continue
   sid=judgment.get('source_id');source=supplied.get(sid)
   if not source:continue
   actual=source.get('sha256','')
   if not re.fullmatch(r'[a-f0-9]{64}',actual):continue
   evidences=judgment.get('evidence',[])
   if not isinstance(evidences,list):continue
   for evidence in evidences:
    if not isinstance(evidence,dict) or evidence.get('source_id') not in {None,'',sid}:continue
    evidence['source_id']=sid
    echoed=evidence.get('pdf_sha256','')
    if echoed and (not isinstance(echoed,str) or (len(echoed)==64 and echoed!=actual) or len(echoed)<64 and (not re.fullmatch(r'[a-f0-9]{16,63}',echoed) or not actual.startswith(echoed))):continue
    quote=evidence.get('quote');block_id=evidence.get('block_id')
    if not isinstance(quote,str) or not quote.strip():continue
    blocks=[b for b in source.get('blocks',[]) if isinstance(block_id,str) and b.get('id')==block_id and normalized(quote) in normalized(b.get('text',''))]
    if not any(normalized(quote) in normalized(text) for text in supplied_texts(package,source)):continue
    if len(blocks)!=1:
     # Missing or mistyped IDs are recovered only from one verbatim match in
     # the supplied blocks of this same fingerprinted PDF.
     blocks=[b for b in source.get('blocks',[]) if normalized(quote) in normalized(b['text'])]
     if len(blocks)==1:block_id=blocks[0]['id']
     elif len(blocks)>1:continue
     else:block_id=None # May be a unique quote spanning adjacent supplied blocks.
    candidate={**evidence,'pdf_sha256':actual}
    if block_id:candidate['block_id']=block_id
    else:candidate.pop('block_id',None)
    try:verify(package,sid,candidate)
    except ValueError:continue
    evidence['pdf_sha256']=actual
    if block_id:evidence['block_id']=block_id
    else:evidence.pop('block_id',None)
 return result
