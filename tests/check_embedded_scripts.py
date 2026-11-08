"""Comprobación de sintaxis JS de las aplicaciones originales con Node.js."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
class Extract(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=False); self.collect=False;self.parts=[];self.scripts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script' and not any(k=='src' for k,v in attrs):self.collect=True;self.parts=[]
 def handle_data(self,data):
  if self.collect:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self.collect:self.scripts.append(''.join(self.parts));self.collect=False
def check(source,name):
 p=subprocess.run(['node','--check'],input=source,text=True,capture_output=True)
 if p.returncode:raise RuntimeError(name+'\n'+p.stderr)
 print('OK',name)
for ed in ('studio','aula'):
 base=ROOT/'web'/ed
 check((base/'desktop-bridge.js').read_text(encoding='utf-8'),ed+' bridge')
 check((base/'central-sync.js').read_text(encoding='utf-8'),ed+' central-sync')
 parser=Extract();parser.feed((base/'index.html').read_text(encoding='utf-8'))
 assert parser.scripts,ed+' sin scripts'
 for i,js in enumerate(parser.scripts,1):check(js,ed+' script '+str(i))
