"""Short request-local references; full provenance is verified after decoding."""
import copy

def encode(data):
 sources=data.get('sources',[])
 if not isinstance(sources,list) or not sources:return data,{}
 refs={};owners={};hashes={}
 for number,source in enumerate(sources,1):
  sid=source['id'];refs[sid]='S'+str(number);hashes[sid]=source.get('sha256')
  for block in source.get('blocks',[]):
   bid=block['id']
   if bid not in refs:refs[bid]='B'+str(len(owners)+1);owners[bid]=sid
 def walk(value,key=''):
  if isinstance(value,dict):return {k:walk(v,k) for k,v in value.items() if k not in {'pdf_sha256','sha256'}}
  if isinstance(value,list):return [walk(v,key) for v in value]
  if isinstance(value,str) and key in {'id','source_id','source_ids','block_id'}:return refs.get(value,value)
  return value
 return walk(data),dict(refs={v:k for k,v in refs.items()},owners=owners,hashes=hashes)

def decode(row,mapping):
 if not mapping or not isinstance(row,dict):return row
 result=copy.deepcopy(row);refs=mapping['refs']
 if not isinstance(result.get('claims'),list):return result
 for claim in result['claims']:
  if not isinstance(claim,dict):continue
  judgments=claim.get('source_judgments',[])
  if not isinstance(judgments,list):continue
  for judgment in judgments:
   if not isinstance(judgment,dict):continue
   alias=judgment.get('source_id');sid=refs.get(alias)
   if sid not in mapping['hashes']:continue
   judgment['source_id']=sid
   evidences=judgment.get('evidence',[])
   if not isinstance(evidences,list):continue
   for evidence in evidences:
    if not isinstance(evidence,dict) or evidence.get('source_id') not in {None,'',alias}:continue
    evidence['source_id']=sid
    bid=refs.get(evidence.get('block_id'))
    if mapping['owners'].get(bid)==sid:evidence['block_id']=bid
    # Never overwrite a conflicting fingerprint returned by the model.
    if 'pdf_sha256' not in evidence:evidence['pdf_sha256']=mapping['hashes'][sid]
 return result
