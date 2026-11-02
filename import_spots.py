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
# DirectWind HTML table
u='https://directwind.com/spots-windsurf.php';s=bs4.BeautifulSoup(S.get(u,timeout=40).text,'html.parser')
for tr in s.select('tr'):
 cells=tr.find_all(['td'])
 if len(cells)<4:continue
 name=cells[0].get_text(' ',strip=True);place=cells[1].get_text(' ',strip=True)
 dept=cells[2].get_text(' ',strip=True)
 if not re.fullmatch(r'(?:\d{2,3}|2A|2B)',dept,re.I):continue
 a=cells[0].find('a',href=True) or tr.find('a',href=True)
 add(name,place,'FR',u,cells[3].get_text(' ',strip=True),requests.compat.urljoin(u,a['href']) if a else '')
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
