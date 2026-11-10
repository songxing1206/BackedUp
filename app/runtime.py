"""Non-secret identity shared by the local server and launcher."""
import hashlib
from pathlib import Path

APP_VERSION='0.5.4-beta'

def instance_id(root):
 return hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]

def health(root):
 return {'app':'backed-up','version':APP_VERSION,'instance':instance_id(root),'status':'ready'}
