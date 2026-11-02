#!/usr/bin/env python3
"""Geoapify place geocoding for 1113 candidate rows. Results are NEVER verified launches."""
import csv, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'spots_1113_koordinaten_pruefung.csv'
CACHE=ROOT/'geocode_1113_cache.json'
OUT=ROOT/'spots_1113_geocoded_candidates.csv'
REPORT=ROOT/'geocode_1113_report.json'
API=os.environ.get('GEOAPIFY_API_KEY','').strip()
LIMIT=max(0,min(int(os.environ.get('MAX_QUERIES','50')),200))
COUNTRIES={'DE':'Germany','FR':'France','NL':'Netherlands'}

def get_result(row):
    cc=row['country'].strip().upper()
    if cc not in COUNTRIES: return {'status':'unsupported_country'}
    # Search for geographic place, not surf launch. Geoapify may return a city or lake centroid.
    query=', '.join(x for x in (row['name'].strip(),row['place'].strip(),COUNTRIES[cc]) if x)
    params=urllib.parse.urlencode({'text':query,'filter':'countrycode:'+cc.lower(),'limit':3,'format':'json','apiKey':API})
    req=urllib.request.Request('https://api.geoapify.com/v1/geocode/search?'+params,headers={'User-Agent':'WindSurfIQ-geocode-1113/1.0'})
    with urllib.request.urlopen(req,timeout=30) as resp: payload=json.load(resp)
    results=payload.get('results',[])
    if not results: return {'status':'no_result'}
    hit=next((h for h in results if h.get('country_code','').upper()==cc and h.get('lat') is not None and h.get('lon') is not None),None)
    if not hit: return {'status':'country_mismatch'}
    return {'status':'candidate_unverified','lat':hit['lat'],'lon':hit['lon'],'formatted':hit.get('formatted',''),
            'result_type':hit.get('result_type',''),'rank_confidence':hit.get('rank',{}).get('confidence','')}

def main():
    if not SOURCE.exists(): sys.exit('Missing spots_1113_koordinaten_pruefung.csv')
    with SOURCE.open(encoding='utf-8-sig',newline='') as f: reader=csv.DictReader(f); rows=list(reader); fields=reader.fieldnames
    if not rows or not {'source_row','name','place','country','candidate_lat','candidate_lon'} <= set(fields or []):
        sys.exit('CSV has unexpected columns or no rows')
    cache=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    used=0; errors=0
    for row in rows:
        key=str(row['source_row']).strip()
        # Don't overwrite preexisting coordinate candidates.
        if row.get('candidate_lat','').strip() and row.get('candidate_lon','').strip(): continue
        if key in cache: continue
        if used>=LIMIT or not API: break
        try:
            cache[key]=get_result(row); used+=1
        except Exception as e:
            errors+=1; print('Geocoding request failed for row',key, type(e).__name__,str(e)[:160],flush=True)
            if errors>=3: break
        time.sleep(1.1)
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    extra=['geocode_lat','geocode_lon','geocode_status','geocode_address','geocode_result_type','geocode_confidence','position_kind']
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields+extra);writer.writeheader()
        for row in rows:
            key=str(row['source_row']).strip();hit=cache.get(key,{})
            preexisting=bool(row.get('candidate_lat','').strip() and row.get('candidate_lon','').strip())
            row.update({'geocode_lat':row.get('candidate_lat','') if preexisting else hit.get('lat',''),
                        'geocode_lon':row.get('candidate_lon','') if preexisting else hit.get('lon',''),
                        'geocode_status':'existing_candidate_unverified' if preexisting else hit.get('status','not_searched'),
                        'geocode_address':hit.get('formatted',''), 'geocode_result_type':hit.get('result_type',''),
                        'geocode_confidence':hit.get('rank_confidence',''),
                        'position_kind':'approximate_place_not_launch' if (preexisting or hit.get('status')=='candidate_unverified') else ''})
            writer.writerow(row)
    report={'total_source_rows':len(rows),'preexisting_candidates':sum(bool(r.get('candidate_lat','') and r.get('candidate_lon','')) for r in rows),
            'new_requests_this_run':used,'cache_entries':len(cache),'new_geocoded_candidates':sum(v.get('status')=='candidate_unverified' for v in cache.values()),
            'request_errors':errors,'api_key_present':bool(API),'warning':'Approximate geocoding positions; no verified launch or parking coordinates.'}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not API: print('No GEOAPIFY_API_KEY secret configured: created output using existing candidates only.')

if __name__=='__main__': main()
