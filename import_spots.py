import requests,bs4,csv,re,json,unicodedata
from pathlib import Path
P=Path(__file__).parent
S=requests.Session();S.headers['User-Agent']='WindSurfIQ catalog importer (research; contact via repository)'
rows=[]
def add(name,place,country,source,activity='',detail=''):
 name=' '.join(name.split());place=' '.join(place.split())
 if name: rows.append(dict(name=name,place=place,country=country,source=source,activity=activity,detail_url=detail,status='source_unverified'))
# Spotara: headings and subsequent location text, country is visible in the page
u='https://spotara.de/spots';s=bs4.BeautifulSoup(S.get(u,timeout=40).text,'html.parser')
for h in s.find_all(['h2','h3']):
 name=h.get_text(' ',strip=True)
 if not name or name.lower().startswith(('surfspots','spots','spotfinder')):continue
 parent=h.parent
 txt=parent.get_text(' ',strip=True)
 m=re.search(r'([^,]{2,80}),\s*(Deutschland|Niederlande|Frankreich)\b',txt)
 if not m:continue
 country={'Deutschland':'DE','Niederlande':'NL','Frankreich':'FR'}[m.group(2)]
 a=h.find_parent('a') or parent.find('a',href=True)
 add(name,m.group(1),country,u,','.join(x for x in ['Windsurfen','Kitesurfen','Wingfoilen'] if x in txt),requests.compat.urljoin(u,a['href']) if a and a.has_attr('href') else '')
# DirectWind: Tabelle kann TH/TD, zusätzliche Spalten oder andere Spaltenreihenfolge haben.
u='https://directwind.com/spots-windsurf.php'
r=S.get(u,timeout=60);r.raise_for_status()
s=bs4.BeautifulSoup(r.text,'html.parser')
directwind_count=0
for tr in s.select('tr'):
 cells=tr.find_all(['th','td'],recursive=False)
 if len(cells)<4: continue
 texts=[c.get_text(' ',strip=True) for c in cells]
 # Abteilungsnummer kann in einer eigenen Zelle stehen, nicht zwingend Index 2.
 dept_index=next((i for i,t in enumerate(texts) if re.fullmatch(r'(?:0?[1-9]|[1-8][0-9]|9[0-5]|97[1-6]|2A|2B)',t,re.I)),None)
 if dept_index is None or dept_index<2: continue
 name,place=texts[0],texts[1]
 if not name or name.lower() in ('nom du spot','spot'): continue
 activity=texts[dept_index+1] if len(texts)>dept_index+1 else ''
 a=cells[0].find('a',href=True) or tr.find('a',href=True)
 add(name,place,'FR',u,activity,requests.compat.urljoin(u,a['href']) if a else '')
 directwind_count+=1
# WICHTIG: Ein grüner GitHub-Workflow darf keinen fehlenden Import verbergen.
if directwind_count<500:
 raise RuntimeError(f'DirectWind: nur {directwind_count} Einträge gelesen (erwartet ca. 677). HTML-Struktur/Seitenabruf prüfen. Spotara-Einträge: {len(rows)-directwind_count}.')
# conservative dedup: identical normalized name and place and country; preserve alternate starts

def norm(v):
 v=unicodedata.normalize('NFKD',v.casefold());v=''.join(c for c in v if not unicodedata.combining(c));return re.sub(r'[^a-z0-9]+','',v)
unique={};dupes=[]
for r in rows:
 key=(r['country'],norm(r['name']),norm(r['place']))
 if key in unique:
  old=unique[key];old['source']+='; '+r['source'];dupes.append(r)
 else:unique[key]=r
fields=['name','place','country','source','activity','detail_url','status']
for fn,items in [('spots_alle_quellen_roh.csv',rows),('spots_nur_exakte_dubletten_entfernt.csv',list(unique.values())),('dubletten_entfernt.csv',dupes)]:
 with (P/fn).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
(P/'importbericht.json').write_text(json.dumps({'source_rows':len(rows),'unique_rows':len(unique),'removed_exact_duplicates':len(dupes),'by_country':{c:sum(r['country']==c for r in unique.values()) for c in ['DE','FR','NL']}},indent=2),encoding='utf-8')
print((P/'importbericht.json').read_text())
