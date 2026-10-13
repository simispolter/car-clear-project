"""Download open vehicle sources. Streaming, SHA256, atomic files, resumable reruns.
Raw public registries are research inputs; the public app never serves licence plates/VINs.
"""
import codecs, argparse, concurrent.futures, csv, datetime, gzip, hashlib, io, json, os, pathlib, time, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]; RAW=ROOT/'data/raw'; RAW.mkdir(parents=True,exist_ok=True)
API='https://data.gov.il/api/3/action/'
CORE={'degem-rechev-wltp','mehir_yevuan','tozeret','recall','amount_monthly_closures_vehicles','rechavim_hashmalim','agg_charge_stations','socharim','musachim','shamaim_rechev','batei-esek'}
EXTENDED={'private-and-commercial-vehicles','shinui_mivne','reshev_bitul_sofi','rechev_le_pail_with_degem','rechev_le_pail_without-degem','personal_import_vehicles','hagbalat_recall','heavy-truck','motorcycle','kli_rechev_ciburiim','kamut_sgirot_hodshi_rechev_blikoddegem','zakaut-hatkana','vehicles_filters_reduce_emissions','hatkana_nekudat_igun'}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def fetch(url):
 for i in range(3):
  try:return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'IndependentVehicleResearch/0.1 (+source-attribution)'}),timeout=90)
  except Exception:
   if i==2:raise
   time.sleep(2**i)
def download(task,force=False):
 key,url,meta=task; out=RAW/(key+'.csv.gz'); side=RAW/(key+'.manifest.json')
 if side.exists() and out.exists() and not force:
  cached=json.loads(side.read_text())
  if cached.get('complete'):return cached
 tmp=out.with_suffix('.tmp'); result={**meta,'url':url,'file':str(out.relative_to(ROOT)),'fetched_at':now(),'complete':False}
 try:
  with fetch(url) as r:
   result['http_status']=r.status; result['last_modified']=r.headers.get('Last-Modified');result['expected_bytes']=int(r.headers.get('Content-Length','0'))
   if 'html' in r.headers.get('Content-Type',''):raise ValueError('HTML response, not CSV')
   h=hashlib.sha256(); size=0
   with gzip.open(tmp,'wb',compresslevel=6) as g:
    while b:=r.read(1024*1024):h.update(b);size+=len(b);g.write(b)
   if result['expected_bytes'] and size!=result['expected_bytes']:raise ValueError('Incomplete response')
  with gzip.open(tmp,'rb') as f: sample=f.read(65536)
  try: codecs.getincrementaldecoder('utf-8-sig')().decode(sample,final=False); encoding='utf-8-sig'
  except UnicodeDecodeError: encoding='cp1255'
  header=sample.decode(encoding,errors='replace').splitlines()[0]; delimiter=max(['|',',',';','\t'],key=header.count)
  result['encoding']=encoding;result['delimiter']=delimiter
  with gzip.open(tmp,'rt',encoding=encoding,errors='replace',newline='') as f:
   warnings=[0]
   def decoded_lines():
    for line in f:
     warnings[0]+=line.count('\ufffd');yield line
   reader=csv.reader(decoded_lines(),delimiter=delimiter); result['columns']=next(reader);result['rows']=sum(1 for _ in reader)
   result['replacement_characters_in_decoded_view']=warnings[0]
  os.replace(tmp,out);result.update(complete=True,bytes=size,compressed_bytes=out.stat().st_size,sha256_uncompressed=h.hexdigest())
 except Exception as e:
  tmp.unlink(missing_ok=True);result['error']=str(e)
 side.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(key,result.get('rows'),result.get('error','OK'),flush=True);return result

def main():
 a=argparse.ArgumentParser();a.add_argument('--extended',action='store_true');a.add_argument('--force',action='store_true');args=a.parse_args()
 catalog=json.load(fetch(API+'package_search?'+urllib.parse.urlencode({'q':'רכב','rows':1000})))
 (RAW/'ckan-vehicle-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
 tasks=[];inventory=[]
 for p in catalog['result']['results']:
  for r in p.get('resources',[]):
   m={'package':p['name'],'title':p['title'],'resource_title':r.get('name'),'resource_id':r['id'],'license_id':p.get('license_id'),'license_title':p.get('license_title'),'license_url':p.get('license_url'),'publisher':p.get('organization',{}).get('title'),'metadata_modified':p.get('metadata_modified'),'format':r.get('format'),'url':r.get('url')}
   selected=p['name'] in CORE or (args.extended and p['name'] in EXTENDED)
   m['scope']='full_download' if selected and r.get('format')=='CSV' else 'mapped_only'
   inventory.append(m)
   if m['scope']=='full_download':tasks.append((r['id'],r['url'],m))
 (ROOT/'data/source-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(lambda t:download(t,args.force),tasks))
 (ROOT/'data/download-manifest.json').write_text(json.dumps({'created_at':now(),'sources':results},ensure_ascii=False,indent=2))
 print('Downloaded',sum(x['complete'] for x in results),'of',len(results),flush=True)
if __name__=='__main__':main()
