"""Experimental local evidence selection; original block text and IDs stay intact."""
import json,re,sqlite3
from contextlib import closing
from .retrieval import query_terms,tokens

VERSION='focused-units-1'
QUALIFIERS='however limitation sample participant method interaction symptom diagnosis representative subgroup significant difference'

def focused_context(claim,context,max_chars=600):
 """Retain nearby antecedents only for anaphoric or dependent claims."""
 if not re.search(r'\b(this|these|those|same|their|they|it|former|latter)\b|上述|该研究|同一样本|这些|那些|^\s*[.,;，；]',claim[:160],re.I):return ''
 at=context.find(claim)
 if at<0:return context[:2000]
 before=context[:at].strip();sentences=re.split(r'(?<=[.!?。！？])\s+',before)
 kept=[];size=0
 for sentence in reversed(sentences):
  if size+len(sentence)>max_chars:break
  kept.insert(0,sentence);size+=len(sentence)
 return ' '.join(kept) if kept or not before else context[:2000]

def select_units(path,query,round_number=0):
 terms=query_terms(query)
 if not terms:return []
 expr=' OR '.join('"'+t+'"' for t in terms)
 gates=' OR '.join('"'+t+'"' for t in tokens(QUALIFIERS))
 with closing(sqlite3.connect(path)) as db:
  def rank(expression):return [x[0] for x in db.execute('SELECT rowid FROM search WHERE search MATCH ? ORDER BY bm25(search),rowid LIMIT 16',(expression,))]
  main=rank(expr);scope=rank('('+expr+') AND ('+gates+')');offset=round_number*4
  chosen=list(dict.fromkeys(n for pair in zip(main[offset:offset+4],scope[offset:offset+4]) for n in pair))
  # zip must not discard a channel when the other has fewer hits.
  chosen+= [n for n in main[offset:offset+4]+scope[offset:offset+4] if n not in chosen]
  units=[]
  for n in chosen:
   row=db.execute('SELECT page,blocks FROM paragraphs WHERE id=?',(n,)).fetchone()
   if not row:continue
   page,raw=row;blocks=json.loads(raw);ids=[n]
   # Extend incomplete sentence groups using adjacent same-page units only.
   for near,prepend in [(n-1,True),(n+1,False),(n+2,False)]:
    edge=blocks[0]['text'] if prepend else blocks[-1]['text']
    if prepend:
     if not re.match(r'^[a-z,;，；]',edge.strip()):continue
    elif re.search(r'[.!?。！？][\s\d\]）)]*$',edge.strip()):break
    adjacent=db.execute('SELECT page,blocks FROM paragraphs WHERE id=?',(near,)).fetchone()
    if not adjacent or adjacent[0]!=page:continue
    extra=json.loads(adjacent[1]);candidate=extra+blocks if prepend else blocks+extra
    if sum(len(b['text']) for b in candidate)>3600:continue
    blocks=candidate;ids.append(near)
   units.append({'order':min(ids),'paragraph_ids':sorted(set(ids)),'blocks':blocks})
 return units

def select_units_with_neighbors(path,query,round_number=0,max_chars=6000):
 """Fixed ablation B: BM25 units plus the adjacent same-page paragraphs.

 The expansion is deterministic, keeps original block IDs/text, removes overlap,
 and drops a neighbor as a whole when it would exceed the per-unit allowance.
 """
 units=select_units(path,query,round_number);expanded=[]
 with closing(sqlite3.connect(path)) as db:
  for unit in units:
   paragraph_ids=unit.get('paragraph_ids') or [unit['order']]
   anchor=db.execute('SELECT page FROM paragraphs WHERE id=?',(unit['order'],)).fetchone()
   before=[];after=[]
   if anchor:
    for paragraph_id,target in [(min(paragraph_ids)-1,before),(max(paragraph_ids)+1,after)]:
     row=db.execute('SELECT page,blocks FROM paragraphs WHERE id=?',(paragraph_id,)).fetchone()
     if row and row[0]==anchor[0]:target.extend(json.loads(row[1]))
   blocks=[];seen=set()
   for group in [before,unit['blocks'],after]:
    additions=[block for block in group if block['id'] not in seen]
    if sum(len(block['text']) for block in blocks+additions)>max_chars:continue
    blocks.extend(additions);seen.update(block['id'] for block in additions)
   expanded.append({**unit,'blocks':blocks,'neighbor_context':True})
 return expanded

def pack_units(sources,max_bytes):
 """Whole selected units only; overlap and identical unit text appear once."""
 result=[];allowance=max_bytes//max(1,len(sources))
 for source in sources:
  header={k:v for k,v in source.items() if k!='units'};header['blocks']=[]
  kept=[];seen=set();texts=set()
  for unit in source.get('units',[]):
   key=' '.join(' '.join(b['text'].split()) for b in unit['blocks'])
   if key in texts:continue
   additions=[b for b in unit['blocks'] if b['id'] not in seen]
   candidate={**header,'blocks':kept+additions}
   if len(json.dumps(candidate,ensure_ascii=False).encode())>allowance:continue
   kept+=additions;seen.update(b['id'] for b in additions);texts.add(key)
  if kept:result.append({**header,'blocks':kept})
 return result
