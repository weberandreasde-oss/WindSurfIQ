#!/usr/bin/env python3
"""Multi-pass geocoding for spot candidates; approximate positions are NOT launches."""
import csv, json, pathlib, re, sys, time, unicodedata, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'spot_kandidaten.csv'; CACHE=ROOT/'geocode_cache.json'; OUT=ROOT/'spot_kandidaten_geocodiert.csv'
COUNTRIES={'DE':'Deutschland','FR':'France','NL':'Nederland'}

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s).casefold()) if not unicodedata.combining(c)).strip()

def variants(r):
    name=r['kandidat'].strip(); region=r['region'].strip(); country=COUNTRIES[r['land']]
    options=[(f'{name}, {country}','spotname'),(f'{name}, {region}, {country}','spotname_region')]
    for part in re.split(r'\s*/\s*|\s+[–—]\s+',name):
        part=part.strip()
        if part and norm(part)!=norm(name) and len(part)>2:
            options.append((f'{part}, {country}','namensbestandteil'))
            options.append((f'{part}, {region}, {country}','namensbestandteil_region'))
    # Only use the region as an approximate fallback if it looks like a local place,
    # not a whole province, coastline, or category (which would produce misleading pins).
    broad={'bretagne','normandie','vendee','var','gironde','fehmarn','ijsselmeer / markermeer',
           'deutschland / nord- und ostsee / binnenland','nord-holland','zuid-holland','provence'}
    if region and norm(region) not in broad and '/' not in region and len(region)<38:
        options.append((f'{region}, {country}','region_naeherung'))
    unique=[]; seen=set()
    for q,method in options:
        if norm(q) not in seen: unique.append((q,method));seen.add(norm(q))
    return unique

def search(query,cc):
    args=urllib.parse.urlencode({'q':query,'format':'jsonv2','limit':3,'countrycodes':cc.lower(),'addressdetails':1})
    req=urllib.request.Request('https://nominatim.openstreetmap.org/search?'+args,headers={
        'User-Agent':'WindSurfIQ-SpotResearch/2.0 (public GitHub project; contact via repository issues)',
        'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

def select(hits,cc):
    for hit in hits:
        if str(hit.get('address',{}).get('country_code','')).upper()==cc and hit.get('lat') and hit.get('lon'):
            return {'lat':hit['lat'],'lon':hit['lon'],'display_name':hit.get('display_name',''),
                    'osm_type':hit.get('type',''),'osm_class':hit.get('class','')}
    return None

def main():
    rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig',newline=''),delimiter=';'))
    if not rows:raise SystemExit('Keine Kandidaten gefunden')
    cache=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    max_requests=int(sys.argv[1]) if len(sys.argv)>1 else 60
    used=0;errors=0
    for row in rows:
        key=norm('|'.join([row['land'],row['region'],row['kandidat']]))
        old=cache.get(key,'__missing__')
        # Preserve successful first-version results, even if not yet checked.
        if isinstance(old,dict) and old.get('lat') and old.get('lon') and 'attempts' not in old:
            cache[key]={'hit':{'lat':old['lat'],'lon':old['lon'],'display_name':old.get('display_name',''),
                               'osm_type':old.get('type',''),'osm_class':old.get('class','')},
                        'method':'altbestand_ungeprueft','attempts':[],'complete':True}
            continue
        if isinstance(old,dict) and 'attempts' in old: entry=old
        else: entry={'hit':None,'method':'','attempts':[],'complete':False}
        if entry.get('hit') or entry.get('complete'):cache[key]=entry;continue
        for query,method in variants(row):
            if query in entry['attempts']:continue
            if used>=max_requests:break
            try: result=select(search(query,row['land']),row['land'])
            except Exception as exc:
                errors+=1;print('Abfragefehler:',query,str(exc),flush=True)
                # Do not mark a failed request as completed: retry in next run.
                break
            used+=1;entry['attempts'].append(query)
            if result:entry['hit']=result;entry['method']=method
            cache[key]=entry
            CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
            time.sleep(1.2)
            if result:break
        if entry.get('hit') or all(q in entry['attempts'] for q,_ in variants(row)):
            entry['complete']=True
        cache[key]=entry
        if used>=max_requests:break
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
    extra=['lat','lon','osm_name','coordinate_accuracy','geocode_status','suchmethode','osm_typ','suchversuche']
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])+extra,delimiter=';');writer.writeheader()
        for row in rows:
            key=norm('|'.join([row['land'],row['region'],row['kandidat']]))
            entry=cache.get(key,{})
            hit=entry.get('hit') if isinstance(entry,dict) else None
            method=entry.get('method','') if isinstance(entry,dict) else ''
            if hit:
                row.update(lat=hit['lat'],lon=hit['lon'],osm_name=hit.get('display_name',''),
                    coordinate_accuracy='ungeprüfte Näherungsposition; kein Wassereinstieg',
                    geocode_status='Treffer – manuelle Prüfung erforderlich',suchmethode=method,
                    osm_typ=hit.get('osm_type',''),suchversuche=len(entry.get('attempts',[])))
            else:
                row.update(lat='',lon='',osm_name='',coordinate_accuracy='',
                    geocode_status='kein Treffer' if entry.get('complete') else 'weitere Suche offen',
                    suchmethode='',osm_typ='',suchversuche=len(entry.get('attempts',[])))
            writer.writerow(row)
    hits=sum(isinstance(v,dict) and bool(v.get('hit')) for v in cache.values())
    unfinished=sum(not (isinstance(cache.get(norm('|'.join([r['land'],r['region'],r['kandidat']]))),dict) and
                       cache[norm('|'.join([r['land'],r['region'],r['kandidat']]))].get('complete')) for r in rows)
    print(f'{len(rows)} Kandidaten, {hits} mit OSM-Suchergebnis, {used} neue Abfragen, {unfinished} noch nicht abgeschlossen, {errors} Anfragefehler')

if __name__=='__main__':main()
