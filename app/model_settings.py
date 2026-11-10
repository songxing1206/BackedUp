"""Local model configuration; credentials never included in public responses."""
from .text_io import read_text_compat
import copy,json,os,threading
from pathlib import Path
from urllib.parse import urlsplit
from .reasoning_policy import validate_reasoning

DEFAULT_URLS={'google':'https://generativelanguage.googleapis.com/v1beta/openai','deepseek':'https://api.deepseek.com','openai':'https://api.openai.com/v1','anthropic':'https://api.anthropic.com/v1'}
DEFAULT_CONFIG={'provider':'custom','model':'deepseek-chat','base_url':'https://models.sjtu.edu.cn/api/v1','session_only':True}
def endpoint(value):
 u=urlsplit(value)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('API地址需要无凭证、无查询参数的 HTTPS 地址')
 return value.rstrip('/')

def validate_provider_endpoint(provider,url):
 if provider in DEFAULT_URLS and endpoint(url)!=DEFAULT_URLS[provider]:
  raise ValueError('所选服务商与 API 地址不一致，请恢复官方地址；第三方地址请使用自定义 API')

class SettingsStore:
 def __init__(self,path):
  self.path=Path(path);self.lock=threading.RLock();self.value={**DEFAULT_CONFIG,'api_key':''}
  if self.path.exists():
   try:self.value.update(json.loads(read_text_compat(self.path)))
   except (ValueError,OSError):pass
 def public(self):
  with self.lock:
   return {**{k:v for k,v in self.value.items() if k!='api_key'},'has_key':bool(self.value.get('api_key'))}
 def snapshot(self):
  with self.lock:return copy.deepcopy(self.value)
 def save(self,fields):
  with self.lock:
   provider=fields.get('provider',self.value.get('provider','deepseek'))
   if provider not in {*DEFAULT_URLS,'custom'}:raise ValueError('当前仅支持模型API，请重新选择服务商并配置API Key')
   model=str(fields.get('model','')).strip()
   if not model:raise ValueError('请填写模型 ID')
   if len(model)>150 or any(c in model for c in '\r\n'):raise ValueError('模型 ID 无效')
   key=str(fields.get('api_key','')).strip()
   same=provider==self.value.get('provider')
   url=endpoint(str(fields.get('base_url') or DEFAULT_URLS.get(provider,'')))
   if provider in DEFAULT_URLS:validate_provider_endpoint(provider,url)
   same=same and url==self.value.get('base_url')
   if not key and same:key=self.value.get('api_key','')
   if fields.get('clear_key'):key=''
   if len(key)>4096 or any(c in key for c in '\r\n'):raise ValueError('API Key 无效')
   value=dict(provider=provider,model=model,base_url=url,api_key=key,session_only=bool(fields.get('session_only',True)),**validate_reasoning(fields,self.value))
   if not value['session_only']:
    self.path.parent.mkdir(parents=True,exist_ok=True)
    tmp=self.path.with_suffix('.tmp');fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    if hasattr(os,'fchmod'):os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False)
    tmp.replace(self.path)
   elif self.path.exists():
    # Preserve non-secret preferences but remove old on-disk credential when moving to session mode.
    fd=os.open(self.path,os.O_WRONLY|os.O_TRUNC,0o600)
    if hasattr(os,'fchmod'):os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as f:json.dump({**value,'api_key':''},f)
   self.value=value;return self.public()
