#!/usr/bin/env python3
"""Geocode known spot candidates, keeping uncertainty explicit.
Run with network access (e.g. GitHub Actions). Never treat geocoded towns as launches.
"""
import csv,json,time,urllib.parse,urllib.request,pathlib,unicodedata,sys
ROOT=pathlib.Path(__file__).resolve().parent
CSV=ROOT/'spot_kandidaten.csv'; CACHE=ROOT/'geocode_cache.json'; OUT=ROOT/'spot_kandidaten_geocodiert.csv'
COUNTRIES={'DE':'Germany','FR':'France','NL':'Netherlands'}
def norm(x):
 return ''.join(c for c in unicodedata.normalize('NFKD',x.casefold()) if not unicodedata.combining(c)).strip()
def lookup(q,cc):
 args=urllib.parse.urlencode({'q':q,'format':'jsonv2','limit':1,'countrycodes':cc.lower(),'addressdetails':1})
 req=urllib.request.Request('https://nominatim.openstreetmap.org/search?'+args,headers={'User-Agent':'WindSurfIQ-Research/1.0 (GitHub open source spot catalog)','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=25) as f:return json.load(f)
def main():
 cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}; rows=list(csv.DictReader(CSV.open(encoding='utf-8-sig',newline=''),delimiter=';'))
 max_requests=int(sys.argv[1]) if len(sys.argv)>1 else 60; used=0
 for row in rows:
  key=norm('|'.join([row['land'],row['region'],row['kandidat']]))
  if key in cache:continue
  if used>=max_requests:break
  # Query name plus regional context; avoid pretending that a town centre is a verified launch.
  query=', '.join(x for x in [row['kandidat'],row['region'],COUNTRIES[row['land']]] if x)
  try:
   found=lookup(query,row['land']);cache[key]=found[0] if found else None
  except Exception as e:
   print('Lookup failed',query,str(e));break
  used+=1;CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2));time.sleep(1.2)
 fields=list(rows[0])+['lat','lon','osm_name','coordinate_accuracy','geocode_status']
 with OUT.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,delimiter=';');w.writeheader()
  for r in rows:
   k=norm('|'.join([r['land'],r['region'],r['kandidat']]));hit=cache.get(k)
   r.update(lat=hit.get('lat','') if hit else '',lon=hit.get('lon','') if hit else '',osm_name=hit.get('display_name','') if hit else '',coordinate_accuracy='ungeprüfte OSM-Suchergebnisposition' if hit else '',geocode_status='Kandidat: manuelle Prüfung erforderlich' if hit else 'offen')
   w.writerow(r)
 print(f'{len(rows)} Kandidaten, {sum(bool(cache.get(norm("|".join([r["land"],r["region"],r["kandidat"]])))) for r in rows)} mit OSM-Suchergebnis, {used} neue Abfragen')
if __name__=='__main__':main()
