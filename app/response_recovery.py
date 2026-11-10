"""Recover only complete claim objects from a truncated review JSON array."""
import json,re

class ResponseError(ValueError):
 def __init__(self,message,raw='',finish_reason=None):
  super().__init__(message);self.raw=raw;self.finish_reason=finish_reason

def complete_claims(raw):
 text=re.sub(r'^```(?:json)?\s*','',str(raw).strip())
 # Decode the top-level prefix so a claims key inside quoted source text cannot match.
 decoder=json.JSONDecoder();pos=1 if text.startswith('{') else len(text)
 while pos<len(text):
  try:
   pos+=len(text[pos:])-len(text[pos:].lstrip());key,end=decoder.raw_decode(text,pos)
   pos=end;pos+=len(text[pos:])-len(text[pos:].lstrip())
   if text[pos:pos+1]!=':':return []
   pos+=1;pos+=len(text[pos:])-len(text[pos:].lstrip())
   if key=='claims' and text[pos:pos+1]=='[':
    pos+=1;claims=[]
    while pos<len(text):
     pos+=len(text[pos:])-len(text[pos:].lstrip())
     try:claim,end=decoder.raw_decode(text,pos)
     except ValueError:
      partial=partial_claim(text[pos:])
      if partial:claims.append(partial)
      break
     if not isinstance(claim,dict):break
     claims.append(claim);pos=end;pos+=len(text[pos:])-len(text[pos:].lstrip())
     if text[pos:pos+1]!=',':break
     pos+=1
    return claims
   _,pos=decoder.raw_decode(text,pos);pos+=len(text[pos:])-len(text[pos:].lstrip())
   if text[pos:pos+1]!=',':return []
   pos+=1
  except (ValueError,IndexError):return []
 return []

def review_response(raw,finish_reason=None):
 try:
  result=json.loads(re.sub(r'\s*```$','',re.sub(r'^```(?:json)?\s*','',str(raw).strip())))
  if not isinstance(result,dict):raise ValueError()
  if finish_reason not in {'length','max_tokens'}:return result
 except ValueError:pass
 return {'claims':complete_claims(raw),'combined':{'status':'无法判断','reason':'模型响应未完整返回，已保留可校验内容'},'_response_incomplete':True,'suggestion':None}

def partial_claim(text):
 """Keep complete judgments inside the final unfinished claim, without inventing text."""
 if not text.startswith('{'):return None
 decoder=json.JSONDecoder();pos=1;claim={}
 try:
  while pos<len(text):
   pos+=len(text[pos:])-len(text[pos:].lstrip());key,pos=decoder.raw_decode(text,pos)
   pos+=len(text[pos:])-len(text[pos:].lstrip())
   if text[pos:pos+1]!=':':return None
   pos+=1;pos+=len(text[pos:])-len(text[pos:].lstrip())
   if key=='source_judgments' and text[pos:pos+1]=='[':
    judgments=[];pos+=1
    while pos<len(text):
     pos+=len(text[pos:])-len(text[pos:].lstrip())
     try:judgment,pos=decoder.raw_decode(text,pos)
     except ValueError:break
     if not isinstance(judgment,dict):break
     judgments.append(judgment);pos+=len(text[pos:])-len(text[pos:].lstrip())
     if text[pos:pos+1]!=',':break
     pos+=1
    return {**claim,'source_judgments':judgments} if judgments and isinstance(claim.get('id'),str) and isinstance(claim.get('text'),str) else None
   value,pos=decoder.raw_decode(text,pos);claim[key]=value
   pos+=len(text[pos:])-len(text[pos:].lstrip())
   if text[pos:pos+1]!=',':return None
   pos+=1
 except (ValueError,IndexError):return None
 return None
