"""Small disk-backed paragraph retrieval; original block IDs remain authoritative."""
import json,re,sqlite3
from contextlib import closing
from pathlib import Path

VERSION='document-paragraph-bm25-numeric-3'
TERMS={'非自杀性自伤':'nssi nonsuicidal self injury','自伤':'self injury harm nssi','青少年':'adolescent youth','自杀意图':'suicidal intent','社会认可':'social culturally sanctioned accepted','情绪':'emotion affect','负强化':'negative reinforcement relief','正强化':'positive reinforcement','抑制控制':'inhibitory inhibition control','复发':'relapse recurrence','重复':'repetitive repeated recurrent','认知':'cognitive cognition','应激':'stress stressful','风险因素':'risk factors','患病率':'prevalence','流行病学':'prevalence epidemiology','冲动':'impulsive impulsivity','强迫':'compulsive compulsivity ocd','学习':'learning','记忆':'memory recall','注意':'attention','自我效能':'self efficacy','调节':'regulation','定义':'defined definition','无自杀':'without suicidal intent','行为':'behavior behavioural','社会文化':'social cultural sanctioned accepted','有意':'deliberate intentional','反复':'repetitive recurrent','精神卫生':'mental health','缓解':'relief alleviate reduce','奖赏':'reward','负性':'negative','负面':'negative','心理':'psychological mental','抑郁':'depression depressive','终生':'lifetime','发生率':'incidence prevalence'}
STOP=set('the a an and or of to in is are was were be been by for with that this it as on at from not no does do et al can may study studies author year'.split())

def tokens(text):
 words=re.findall(r'[a-z]+|\d+(?:\.\d+)?',text.lower())
 return [w[:-1] if len(w)>4 and w.endswith('s') and not w.endswith('ss') else w for w in words if w not in STOP]

def query_terms(text):
 text=re.sub(r'[（(][^）)]*[A-Za-z][^）)]*(?:19|20)\d{2}[^）)]*[）)]','',text)
 translated=' '.join(value for key,value in TERMS.items() if key in text)
 return list(dict.fromkeys(tokens(text+' '+translated)))[:40]

NUMERIC_CUES={'mean','average','range','ranged','maximum','minimum','median','percent','percentage','sd','ci','days','day','months','month','weeks','week','years','year','hours','hour','times','participants','patients'}

def numeric_values(text):
 """Return claim numbers, excluding ordinary citation years.

 Matching is deliberately only a retrieval signal.  A shared number never
 becomes evidence or a semantic verdict here.
 """
 text=re.sub(r'[（(][^）)]*[A-Za-z][^）)]*(?:19|20)\d{2}[^）)]*[）)]',' ',text)
 values=[]
 for raw in re.findall(r'(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?',text):
  try:values.append(float(raw.rstrip('%').replace(',','')))
  except ValueError:pass
 return values

def numeric_score(query,text):
 wanted=numeric_values(query)
 if not wanted:return 0
 found=numeric_values(text)
 score=0
 for value in wanted:
  best=0
  for candidate in found:
   if abs(value-candidate)<1e-9:best=max(best,4)
   # Claims commonly round a reported mean (52) from a decimal (52.19).
   elif value.is_integer() and abs(value-candidate)<0.5:best=max(best,2)
  score+=best
 if not score:return 0
 query_words=set(tokens(query));text_words=set(tokens(text))
 score+=min(3,len(query_words&text_words&NUMERIC_CUES))
 return score

def paragraphs(index):
 document=index.get('document') or {}
 if document.get('paragraphs'):
  by_id={block['id']:block for page in index['pages'] for block in page['blocks']}
  references=False
  for paragraph in document['paragraphs']:
   if paragraph.get('role')=='heading' and paragraph.get('normalized_text','').strip().casefold() in {'references','bibliography','literature cited','参考文献'}:references=True
   if references:continue
   blocks=[]
   for block_id in paragraph.get('block_ids',[]):
    block=by_id.get(block_id)
    if block:blocks.append(dict(id=block['id'],text=block['text'],physical_page=block['physical_page']))
   if blocks:yield paragraph['physical_page'],blocks
  return
 references=False
 for page in index['pages']:
  group=[];size=0
  for block in page['blocks']:
   if block['text'].strip().casefold() in {'references','bibliography','literature cited'}:references=True
   if references:continue
   if group and (len(group)>=8 or size+len(block['text'])>1200):yield page['physical_page'],group;group=[];size=0
   group.append(dict(id=block['id'],text=block['text'],physical_page=page['physical_page']));size+=len(block['text'])
  if group:yield page['physical_page'],group

class Retriever:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 def build(self,index):
  target=self.root/(index['sha256']+'-'+index.get('parser_version','unknown')+'-'+VERSION+'.sqlite')
  if target.exists():return target
  temp=target.with_suffix('.tmp');temp.unlink(missing_ok=True)
  try:
   with closing(sqlite3.connect(temp)) as db, db:
    db.execute('CREATE TABLE paragraphs(id INTEGER PRIMARY KEY,page INTEGER,blocks TEXT)')
    db.execute('CREATE VIRTUAL TABLE search USING fts5(words)')
    for n,(page,blocks) in enumerate(paragraphs(index),1):
     db.execute('INSERT INTO paragraphs VALUES(?,?,?)',(n,page,json.dumps(blocks,ensure_ascii=False)))
     db.execute('INSERT INTO search(rowid,words) VALUES(?,?)',(n,' '.join(tokens(' '.join(b['text'] for b in blocks)))))
   temp.replace(target)
  except BaseException:temp.unlink(missing_ok=True);raise
  return target
 def select(self,path,query,round_number=0):
  terms=query_terms(query)
  if not terms and not numeric_values(query):return []
  expression=' OR '.join('"'+term+'"' for term in terms)
  with closing(sqlite3.connect(path)) as db:
   ranked=[r[0] for r in db.execute('SELECT rowid FROM search WHERE search MATCH ? ORDER BY bm25(search),rowid LIMIT 24',(expression,))] if expression else []
   numeric=[]
   if numeric_values(query):
    for rowid,blocks in db.execute('SELECT id,blocks FROM paragraphs'):
     score=numeric_score(query,' '.join(b['text'] for b in json.loads(blocks)))
     if score:numeric.append((-score,rowid))
    # Numeric candidates supplement BM25 but retain deterministic ordering.
    ranked=[rowid for _,rowid in sorted(numeric)[:8]]+ranked
    ranked=list(dict.fromkeys(ranked))
   # Expand only to new candidates in the second round; do not resend first-round paragraphs.
   ranked=ranked[:8] if round_number==0 else ranked[8:16]
   rows=[];seen=set()
   priorities=[(n,n) for n in ranked]+[(n,nearby) for n in ranked for nearby in [n-1,n+1]]
   for n,nearby in priorities:
    if nearby in seen:continue
    row=db.execute('SELECT page,blocks FROM paragraphs WHERE id=?',(nearby,)).fetchone()
    current=db.execute('SELECT page FROM paragraphs WHERE id=?',(n,)).fetchone()
    if row and row[0]==current[0]:rows.extend(json.loads(row[1]));seen.add(nearby)
  return list({block['id']:block for block in rows}.values())

def pack_sources(sources,max_bytes):
 """Fairly allocate the candidate allowance across all cited sources, without truncating blocks."""
 result=[];allowance=max_bytes//max(1,len(sources))
 for source in sources:
  blocks=[];size=len(json.dumps({**source,'blocks':[]},ensure_ascii=False).encode())
  for block in source['blocks']:
   cost=len(json.dumps(block,ensure_ascii=False).encode())+2
   if size+cost>allowance:continue
   blocks.append(block);size+=cost
  if blocks:result.append({**source,'blocks':blocks})
 return result
