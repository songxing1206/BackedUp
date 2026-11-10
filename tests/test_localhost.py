import unittest
from types import SimpleNamespace
from unittest.mock import patch
import launcher,server

class LocalhostTests(unittest.TestCase):
 def test_browser_opens_localhost(self):
  with patch('launcher.webbrowser.open') as opened:
   launcher.open_page(8788,True);opened.assert_called_once_with('http://localhost:8788/')
 def test_host_and_origin_remain_restricted(self):
  for host,origin,expected in [('localhost:8787',None,True),('localhost:8787','http://localhost:8787',True),('127.0.0.1:8787','http://127.0.0.1:8787',True),('localhost:8787','https://evil.example',False),('evil.example:8787',None,False),('localhost:8788',None,False),('localhost:8787','http://127.0.0.1:8787',False)]:
   with self.subTest(host=host,origin=origin):
    headers={'Host':host}
    if origin:headers['Origin']=origin
    handler=SimpleNamespace(headers=headers,server=SimpleNamespace(server_port=8787))
    self.assertEqual(server.Handler.allowed(handler),expected)
