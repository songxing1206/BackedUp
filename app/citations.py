"""Original-offset adapter for the MIT CiteFact APA parser."""
import re
from .vendor.citefact.apa import ApaParser, _ZOTERO_MARKDOWN_LINK

def _normalized(text):
 out=[]; mapping=[]; cursor=0
 for m in _ZOTERO_MARKDOWN_LINK.finditer(text):
  out.extend(text[cursor:m.start()]); mapping.extend(range(cursor,m.start()))
  value=m.group(1); out.extend(value); mapping.extend(range(m.start(1),m.end(1))); cursor=m.end()
 out.extend(text[cursor:]);mapping.extend(range(cursor,len(text)))
 normalized=''.join(out).translate(str.maketrans({'（':'(', '）':')', '；':';', '，':','}))
 # Normalize Chinese narrative suffixes without changing original offsets.
 normalized=re.sub(r'(?<=[A-Za-z])\s*等(?:学者|人)?(?=\s*\(\d{4})',lambda m:' '*len(m.group()),normalized)
 # Mask non-prose without changing offsets.
 normalized=re.sub(r'```[^\n]*\n.*?(?:```|\Z)',lambda m: ''.join('\n' if c=='\n' else ' ' for c in m.group()),normalized,flags=re.S)
 normalized=re.sub(r'`[^`\n]*`',lambda m:' '*len(m.group()),normalized)
 heading=re.search(r'^\s*(?:#{1,6}\s*)?(?:References|Bibliography|参考文献)\s*[:：]?\s*$',normalized,re.M|re.I)
 if heading: normalized=normalized[:heading.start()]+' '*(len(normalized)-heading.start())
 return normalized,mapping

def _sentence(text,start,end):
 pstart=text.rfind('\n\n',0,start)+2 if '\n\n' in text[:start] else 0
 pend=text.find('\n\n',end);pend=len(text) if pend<0 else pend
 para=text[pstart:pend]
 boundaries=[pstart]
 scan=re.sub(r'\]\([^)]*\)',lambda m:' '*len(m.group()),para)
 for m in re.finditer(r'[。！？!?]|\.(?=\s+[A-Z]|\s*$)',scan): boundaries.append(pstart+m.end())
 left=max([b for b in boundaries if b<=start],default=pstart)
 right=min([b for b in boundaries if b>=end],default=pend)
 return text[left:right].strip(),para.strip()

def extract_locations(text,split_grouped=True):
 normalized,mapping=_normalized(text)
 citations=ApaParser().extract(normalized)
 groups={}
 parens=list(re.finditer(r'\([^()]*\)',normalized))
 for c in citations:
  enclosing=next((m for m in parens if m.start()<=c.start and c.end<=m.end()),None)
  # Narrative starts before the year parentheses and should keep its author.
  a,b=(enclosing.start(),enclosing.end()) if enclosing else (c.start,c.end)
  groups.setdefault((a,b),[]).append(c)
 locations=[];citation_index=0
 for group_index,((a,b),members) in enumerate(sorted(groups.items()),1):
  group_start=mapping[a];group_end=mapping[b-1]+1;group_id=f'G{group_index:03d}'
  sentence,context=_sentence(text,group_start,group_end)
  if not split_grouped:
   lid=f'C{group_index:03d}'
   locations.append(dict(id=lid,start=group_start,end=group_end,raw=text[group_start:group_end],sentence=sentence,context=context,line=text.count('\n',0,group_start)+1,members=[dict(id=f'{lid}-R{i}',author=c.author_string,year=str(c.year),raw=c.raw,locator=c.locator) for i,c in enumerate(members,1)]))
   continue
  # Each author-year marker is an independent review unit.  Preserve the
  # enclosing group so the UI can still explain that two markers came from the
  # same parenthesis without allowing one source failure to erase the other.
  for member_index,c in enumerate(members,1):
   citation_index+=1;lid=f'C{citation_index:03d}'
   start=mapping[c.start];end=mapping[c.end-1]+1
   member=dict(id=f'{lid}-R1',author=c.author_string,year=str(c.year),raw=c.raw,locator=c.locator)
   locations.append(dict(id=lid,start=start,end=end,raw=text[start:end],sentence=sentence,context=context,line=text.count('\n',0,start)+1,members=[member],citation_group_id=group_id,citation_group_index=member_index,citation_group_size=len(members),group_start=group_start,group_end=group_end,group_raw=text[group_start:group_end]))
 for loc in locations:loc.update(citation_scope(text,loc,locations))
 warnings=[]
 if re.search(r'\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]',normalized):warnings.append('发现数字引用；当前框架仅处理作者—年份引用，数字引用未被核查。')
 if not locations:warnings.append('未识别到支持格式的引用；这不代表稿件没有引用。')
 warnings.append('来源匹配与语义支持分别判断；模型结论应结合原文证据由作者复核。')
 return dict(locations=locations,warnings=warnings,citation_unit_version=2 if split_grouped else 1)

def citation_scope(text,loc,locations):
 """Assign successive citation groups their own clause; preserve the full sentence as context."""
 if loc.get('citation_group_size',1)>1:return {'claim_text':loc['sentence'],'scope_version':2}
 peers=[p for p in locations if p['sentence']==loc['sentence'] and p['context']==loc['context'] and abs(p['start']-loc['start'])<=len(loc['sentence'])]
 peers.sort(key=lambda p:p['start'])
 if len(peers)<=1:return {'claim_text':loc['sentence'],'scope_version':1}
 index=next(i for i,p in enumerate(peers) if p['id']==loc['id'])
 # Narrative references precede their claim. Keep them intact rather than guess ownership.
 if any(not p.get('group_raw',p['raw']).startswith(('(','（')) for p in peers):return {'claim_text':loc['sentence'],'scope_version':2}
 sentence_start=text.find(loc['sentence'],max(0,loc['start']-len(loc['sentence'])))
 start=peers[index-1].get('group_end',peers[index-1]['end']) if index else sentence_start
 if start<0:start=max(0,loc['start']-len(loc['sentence']))
 end=loc.get('group_end',loc['end'])
 if index==len(peers)-1:
  if sentence_start>=0:end=sentence_start+len(loc['sentence'])
 return {'claim_text':text[start:end].strip(' \n\t，,；;'),'scope_version':2}
