"""Explicit thinking profiles; output allowance includes reasoning and answer."""
POLICY_VERSION='reasoning-budget-1'
DEFAULTS=dict(reasoning_effort='high',reasoning_output_tokens=32768,reasoning_timeout_seconds=1800)

def reasoning_model(settings):
 return settings.get('provider') in {'deepseek','custom'} and str(settings.get('model','')).casefold()=='deepseek-reasoner'

def validate_reasoning(fields,previous=None):
 values={key:fields.get(key,(previous or {}).get(key,default)) for key,default in DEFAULTS.items()}
 if values['reasoning_effort'] not in {'low','high','max'}:raise ValueError('思考强度需要选择 low、high 或 max')
 for key,allowed in [('reasoning_output_tokens',{16384,32768,65536}),('reasoning_timeout_seconds',{600,1200,1800,3600})]:
  if type(values[key])!=int or values[key] not in allowed:raise ValueError('思考模式额度或等待上限无效')
 return values

def request_profile(settings):
 if not reasoning_model(settings):return None
 values=validate_reasoning(settings)
 return dict(version=POLICY_VERSION,thinking='enabled',effort=values['reasoning_effort'],output_tokens=values['reasoning_output_tokens'],timeout_seconds=values['reasoning_timeout_seconds'])
