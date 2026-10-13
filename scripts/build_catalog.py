"""Build an atomically replaced, indexed SQLite catalogue from full source snapshots."""
import collections,csv,datetime,gzip,hashlib,json,pathlib,sqlite3,os
ROOT=pathlib.Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw'
MODELS='142afde2-6228-49f9-8a29-9b6c3a0cbe40';PRICES='39f455bf-6db0-4926-859d-017f34eacbcb';COUNTS='5e87a7a1-2f6f-41c1-8aec-7216d52a6cf6'
def records(key):
 m=json.loads((RAW/(key+'.manifest.json')).read_text())
 with gzip.open(RAW/(key+'.csv.gz'),'rt',encoding=m.get('encoding','utf-8-sig'),newline='') as f:yield from csv.DictReader(f,delimiter=m.get('delimiter','|'))
def number(v,positive=False):
 try:
  n=float(str(v).strip().replace(',',''))
  if not __import__('math').isfinite(n) or (positive and n<=0):return None
  return int(n) if n.is_integer() else n
 except (ValueError,TypeError):return None
def key(r):
 parts=[str(r.get(c,'')).strip() for c in ('sug_degem','tozeret_cd','degem_cd','shnat_yitzur')]
 return (parts[0],*(str(int(v)) if v.isdigit() else v for v in parts[1:]))
def drive_type(r):
 if 'חשמל' in r.get('delek_nm','') and 'בנזין' not in r.get('delek_nm',''):return 'electric'
 t=r.get('technologiat_hanaa_nm','')
 if any(x in t for x in ['נטענ','PLUG','פלאג']):return 'plugin'
 if 'היבריד' in t or 'היבריד' in r.get('delek_nm',''):return 'hybrid'
 if 'דיזל' in r.get('delek_nm',''):return 'diesel'
 if 'בנזין' in r.get('delek_nm',''):return 'petrol'
 return 'other'
def build():
 for k in (MODELS,PRICES,COUNTS):
  m=json.loads((RAW/(k+'.manifest.json')).read_text())
  if not m['complete']:raise RuntimeError('Incomplete required source: '+k)
 price=collections.defaultdict(list)
 for r in records(PRICES):
  p=number(r.get('mehir'),True)
  if p:price[key(r)].append((p,r.get('shem_yevuan','')))
 counts={key(r):r for r in records(COUNTS)}
 out=ROOT/'data/catalog.sqlite';tmp=out.with_suffix('.building');tmp.unlink(missing_ok=True)
 db=sqlite3.connect(tmp)
 db.executescript('''CREATE TABLE cars(id TEXT PRIMARY KEY,kind TEXT,maker_code TEXT,model_code TEXT,make TEXT,model TEXT,technical_model TEXT,year INTEGER,trim TEXT,body TEXT,fuel TEXT,drive_type TEXT,seats INTEGER,doors INTEGER,power_hp INTEGER,engine_cc INTEGER,automatic INTEGER,airbags INTEGER,co2_wltp REAL,safety_equipment_level INTEGER,price INTEGER,price_max INTEGER,price_options INTEGER,importer TEXT,active_count INTEGER,inactive_count INTEGER,source_row TEXT,identity_conflict INTEGER DEFAULT 0,consumption_l100 REAL,consumption_cycle TEXT,consumption_url TEXT,consumption_reviewed_at TEXT,isofix_count INTEGER,child_fit TEXT,child_fit_url TEXT,child_fit_reviewed_at TEXT,raw_json TEXT);
 CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);''')
 seen=collections.Counter();audit={'source_rows':0,'exact_duplicates':0,'identity_conflicts':0,'price_conflicts':0,'unmatched_price_keys':0};used_prices=set();rows=[]
 for source_line,r in enumerate(records(MODELS),start=2):
  audit['source_rows']+=1;k=key(r);raw=json.dumps(r,ensure_ascii=False,sort_keys=True);uid=hashlib.sha256('|'.join(k).encode()).hexdigest()[:16]
  seen[uid]+=1
  if seen[uid]>1:
   uid+='-'+hashlib.sha256(raw.encode()).hexdigest()[:8];audit['identity_conflicts']+=1
  opts=sorted(set(price.get(k,[])));vals=sorted(set(x[0] for x in opts));p=vals[0] if len(vals)==1 else None
  if vals:used_prices.add(k)
  if len(vals)>1:audit['price_conflicts']+=1
  n=counts.get(k,{})
  rows.append((uid,k[0],k[1],k[2],r.get('tozar') or r.get('tozeret_nm'),r.get('kinuy_mishari') or r.get('degem_nm'),r.get('degem_nm'),number(r.get('shnat_yitzur')),r.get('ramat_gimur'),r.get('merkav'),r.get('delek_nm'),drive_type(r),number(r.get('mispar_moshavim'),True),number(r.get('mispar_dlatot'),True),number(r.get('koah_sus'),True),number(r.get('nefah_manoa'),True),number(r.get('automatic_ind')),number(r.get('mispar_kariot_avir'),True),number(r.get('CO2_WLTP'),True),number(r.get('ramat_eivzur_betihuty')),p,max(vals) if vals else None,len(vals),opts[0][1] if len(opts)==1 else None,number(n.get('mispar_rechavim_pailim')),number(n.get('mispar_rechavim_le_pailim')),str(source_line),int(seen[hashlib.sha256('|'.join(k).encode()).hexdigest()[:16]]>1),None,None,None,None,None,None,None,None,raw))
 try:db.executemany('INSERT INTO cars VALUES('+','.join('?'*37)+')',rows)
 except sqlite3.IntegrityError:raise RuntimeError('Source contains duplicate identities; review before publication')
 # An enrichment is usable only for an exact catalogue ID, with an explicit reviewer and source.
 supplement=ROOT/'data/verified-enrichment.json'
 if supplement.exists():
  for r in json.loads(supplement.read_text()):
   if not r.get('reviewed_by') or not r.get('reviewed_at'):raise ValueError('Enrichment needs reviewer and date')
   if r.get('consumption_l100') is not None:
    if not r.get('consumption_url','').startswith('https://') or r.get('consumption_cycle') not in ['WLTP','NEDC','EPA']:raise ValueError('Consumption requires source and test cycle')
    v=number(r['consumption_l100'],True)
    if v is None:raise ValueError('Invalid consumption')
    db.execute('UPDATE cars SET consumption_l100=?,consumption_cycle=?,consumption_url=?,consumption_reviewed_at=? WHERE id=?',(v,r['consumption_cycle'],r['consumption_url'],r['reviewed_at'],r['id']))
   if r.get('child_fit') is not None:
    if not r.get('child_fit_url','').startswith('https://'):raise ValueError('Child fit requires a test/source')
    db.execute('UPDATE cars SET child_fit=?,child_fit_url=?,child_fit_reviewed_at=?,isofix_count=? WHERE id=?',(json.dumps(r['child_fit'],ensure_ascii=False),r['child_fit_url'],r['reviewed_at'],r.get('isofix_count'),r['id']))
 audit['unmatched_price_keys']=len(set(price)-used_prices)
 db.executescript('CREATE INDEX filter_year ON cars(year);CREATE INDEX filter_price ON cars(price);CREATE INDEX filter_seats ON cars(seats);CREATE INDEX maker ON cars(make);CREATE INDEX family ON cars(make,model,year);CREATE INDEX drivetrain ON cars(drive_type);')
 summary=dict(audit,catalog_rows=len(rows),families=db.execute('SELECT count(*) FROM (SELECT DISTINCT make,model FROM cars)').fetchone()[0],makes=db.execute('SELECT count(DISTINCT make) FROM cars').fetchone()[0],price_covered=sum(r[20] is not None for r in rows),co2_covered=sum(r[18] is not None for r in rows),seats_covered=sum(r[12] is not None for r in rows),consumption_covered=db.execute('SELECT count(*) FROM cars WHERE consumption_l100 IS NOT NULL').fetchone()[0],built_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_fetched_at=json.loads((RAW/(MODELS+'.manifest.json')).read_text())['fetched_at'])
 db.execute('INSERT INTO metadata VALUES(?,?)',('summary',json.dumps(summary,ensure_ascii=False)));db.commit();db.close();os.replace(tmp,out)
 (ROOT/'data/catalog-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':build()
