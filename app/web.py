import datetime,html,json,os,pathlib,sqlite3,urllib.parse,secrets
from flask import Flask,abort,g,jsonify,render_template,request,Response,url_for
from .insights import MIN_ACTIVE, present_car, vehicle_profile, photos
ROOT=pathlib.Path(__file__).resolve().parents[1]
LABELS={'petrol':'בנזין','diesel':'דיזל','hybrid':'היברידי','plugin':'פלאג־אין','electric':'חשמלי','other':'אחר / לא ידוע'}
MODEL_SOURCE='https://data.gov.il/he/datasets/ministry_of_transport/degem-rechev-wltp/142afde2-6228-49f9-8a29-9b6c3a0cbe40'
PRICE_SOURCE='https://data.gov.il/he/datasets/ministry_of_transport/mehir_yevuan/39f455bf-6db0-4926-859d-017f34eacbcb'
class InvalidFilter(ValueError):pass

def validated_int(args,name,default=None,low=0,high=10_000_000):
 v=args.get(name,'')
 if v=='':return default
 try:n=int(v)
 except (ValueError,TypeError):raise InvalidFilter('ערך לא תקין: '+name)
 if not low<=n<=high:raise InvalidFilter('ערך מחוץ לטווח: '+name)
 return n

def compile_filters(args):
 clauses=['active_count>?'];values=[MIN_ACTIVE];f={'q':args.get('q','').strip()[:100],'make':args.get('make','')[:100],'kind':args.get('kind','P'),'drive':args.get('drive',''),'sort':args.get('sort','popular')}
 if f['kind'] not in ['P','M','all']:raise InvalidFilter('סוג רכב לא תקין')
 if f['sort'] not in ['popular','price','newest','co2']:raise InvalidFilter('מיון לא תקין')
 if f['drive'] and f['drive'] not in LABELS:raise InvalidFilter('סוג הנעה לא תקין')
 for name,lo,hi,default in [('budget',1,10000000,None),('year_min',1990,2035,2024 if 'year_min' not in args else None),('seats',1,60,None),('children',0,3,0),('co2',1,1000,None),('page',1,100000,1)]:f[name]=validated_int(args,name,default,lo,hi)
 if f['q']:
  escaped=f['q'].replace('\\','\\\\').replace('%','\\%').replace('_','\\_');clauses.append("(make LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' OR technical_model LIKE ? ESCAPE '\\')");values.extend(['%'+escaped+'%']*3)
 f['body']=args.get('body','')
 if f['body'] not in ['', 'פנאי-שטח', "הצ'בק", 'סדאן', 'סטיישן', 'MPV', 'קופה', 'קבריולט', 'קומבי', 'ואן/נוסעים']:raise InvalidFilter('סוג מרכב לא תקין')
 f['budget_min']=validated_int(args,'budget_min',None,1,10000000)
 f['power_min']=validated_int(args,'power_min',None,1,2000)
 if f['budget'] is not None and f['budget_min'] is not None and f['budget_min']>f['budget']:raise InvalidFilter('טווח מחיר לא תקין')
 for name,col in [('make','make'),('drive','drive_type'),('body','body')]:
  if f[name]:clauses.append(col+'=?');values.append(f[name])
 if f['kind']!='all':clauses.append('kind=?');values.append(f['kind'])
 for name,col,op in [('budget','price','<='),('budget_min','price','>='),('power_min','power_hp','>='),('year_min','year','>='),('seats','seats','>='),('co2','co2_wltp','<=')]:
  if f[name] is not None:clauses.append(col+op+'?');values.append(f[name])
 # A broad shortlist only: seats/doors do not constitute a verified child-seat installation.
 if f['children']:
  clauses.extend(['seats>=?','doors>=4']);values.append(f['children']+2)
 if f['co2'] is not None:clauses.append("drive_type IN ('petrol','diesel','hybrid')")
 f['fit_only']=args.get('fit_only')=='1'
 if f['fit_only']:
  clauses.append('child_fit IS NOT NULL')
  # JSON explicitly records the maximum number of seats checked together.
  clauses.append("CAST(json_extract(child_fit,'$.seats_tested') AS INTEGER)>=?");values.append(f['children'] or 1)
 f['consumption']=validated_int(args,'consumption',None,1,30)
 if f['consumption']:clauses.append("consumption_l100<=? AND consumption_cycle='WLTP'");values.append(f['consumption'])
 order={'popular':'COALESCE(active_count,0) DESC,year DESC,id','price':'price IS NULL,price ASC,year DESC,id','newest':'year DESC,COALESCE(active_count,0) DESC,id','co2':'co2_wltp IS NULL,co2_wltp ASC,year DESC,id'}[f['sort']]
 return (' WHERE '+' AND '.join(clauses) if clauses else ''),values,order,f

def create_app(test_config=None):
 app=Flask(__name__);vercel_host=os.environ.get('VERCEL_URL');app.config.update(DATABASE=os.environ.get('DATABASE_PATH',str(ROOT/'data/catalog.sqlite')),BASE_URL=(os.environ.get('BASE_URL') or os.environ.get('RENDER_EXTERNAL_URL') or ('https://'+vercel_host if vercel_host else 'http://localhost:8000')).rstrip('/'),MAX_CONTENT_LENGTH=65536)
 if test_config:app.config.update(test_config)
 def db():
  if 'db' not in g:
   g.db=sqlite3.connect('file:'+app.config['DATABASE']+'?mode=ro',uri=True);g.db.row_factory=sqlite3.Row
  return g.db
 @app.teardown_appcontext
 def close_db(exception):
  if 'db' in g:g.db.close()
 def editorial():
  p=ROOT/'data/editorial-pages.json'
  return json.loads(p.read_text()) if p.exists() else {}
 def summary():return json.loads(db().execute("SELECT value FROM metadata WHERE key='summary'").fetchone()[0])
 def public_car(row):
  # Explicit projection: never leak raw vehicle records or plate-level data via API.
  return present_car(row)
 def search(args,page_size=18):
  w,v,order,f=compile_filters(args);total=db().execute('SELECT count(*) FROM cars'+w,v).fetchone()[0]
  rows=db().execute('SELECT * FROM cars'+w+' ORDER BY '+order+' LIMIT ? OFFSET ?',v+[page_size,(f['page']-1)*page_size]).fetchall()
  return [public_car(r) for r in rows],total,f
 @app.context_processor
 def common():
  def page_url(page):
   a=request.args.to_dict();a['page']=page;return url_for('catalog')+'?'+urllib.parse.urlencode(a)
  def family_url(car):return url_for('catalog')+'?'+urllib.parse.urlencode({'make':car['make'],'q':car['model'],'kind':'all','year_min':''})
  return dict(min_active=MIN_ACTIVE,photo_credits=photos(),market_sources=json.loads((ROOT/'data/market-sources.json').read_text()),csp_nonce=g.get('csp_nonce',''),labels=LABELS,model_source=MODEL_SOURCE,price_source=PRICE_SOURCE,page_url=page_url,family_url=family_url,base_url=app.config['BASE_URL'])
 app.jinja_env.filters['num']=lambda n:f'{n:,.0f}' if n is not None else 'לא ידוע'
 @app.before_request
 def nonce():g.csp_nonce=secrets.token_urlsafe(18)
 @app.after_request
 def headers(r):
  r.headers['X-Content-Type-Options']='nosniff';r.headers['Referrer-Policy']='strict-origin-when-cross-origin'
  r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' 'nonce-"+g.csp_nonce+"'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
  if request.path.startswith('/api/'):r.headers['Cache-Control']='public, max-age=60'
  return r
 @app.errorhandler(InvalidFilter)
 def invalid(e):
  if request.path.startswith('/api/'):return jsonify(error=str(e)),400
  return render_template('error.html',title='בדקו את החיפוש',message=str(e)),400
 @app.errorhandler(404)
 def missing(e):return render_template('error.html',title='העמוד לא נמצא',message='אפשר לחזור לקטלוג ולחפש רכב אחר.'),404
 @app.get('/')
 def home():
  rows,total,f=search({'kind':'P','year_min':'2024'})
  featured=db().execute("SELECT * FROM cars WHERE make='ב מ וו' AND model='I4 M50' AND year=2022 AND active_count>? ORDER BY active_count DESC LIMIT 1",(MIN_ACTIVE,)).fetchone()
  ranking=db().execute("SELECT make,model,body,SUM(active_count) AS total FROM cars WHERE year=2025 AND kind='P' AND active_count>? GROUP BY make,model ORDER BY total DESC LIMIT 5",(MIN_ACTIVE,)).fetchall()
  return render_template('home.html',featured=public_car(featured) if featured else rows[0],ranking=ranking,stats=summary(),cars=rows[:6],title='רכב ברור — בוחרים רכב בשפה פשוטה',description='קטלוג עצמאי של דגמי הרכב בישראל. מחירים רשמיים, מושבים והשוואה ברורה עם מקורות לכל נתון.')
 @app.get('/cars')
 def catalog():
  cars,total,f=search(request.args);makes=[r[0] for r in db().execute('SELECT DISTINCT make FROM cars WHERE active_count>10 ORDER BY make')]
  return render_template('catalog.html',cars=cars,total=total,f=f,makes=makes,stats=summary(),pages=(total+17)//18,title='קטלוג הרכבים — חיפוש והשוואה',noindex=bool(request.args),description='חפשו דגמים ושנות ייצור לפי מחירון חדש, הנעה, מושבים ונתוני WLTP.')
 @app.get('/cars/<car_id>')
 def detail(car_id):
  r=db().execute('SELECT * FROM cars WHERE id=?',(car_id,)).fetchone()
  if not r or r['active_count'] is None or r['active_count']<=MIN_ACTIVE:abort(404)
  c=public_car(r);raw=json.loads(r['raw_json']);s=summary();profile=vehicle_profile(db(),c,raw)
  schema={'@context':'https://schema.org','@type':'Car','name':c['make']+' '+c['model']+' '+str(c['year']),'vehicleModelDate':str(c['year']),'brand':{'@type':'Brand','name':c['make']},'model':c['model'],'vehicleConfiguration':c['trim'] or c['technical_model'],'url':app.config['BASE_URL']+url_for('detail',car_id=c['id'])}
  if c['seats']:schema['seatingCapacity']=c['seats']
  return render_template('detail.html',car=c,profile=profile,raw=raw,stats=s,schema=schema,title=c['make']+' '+c['model']+' '+str(c['year'])+' — מפרט והשוואה',description='מידע על '+c['make']+' '+c['model']+' שנת '+str(c['year'])+' ורמת גימור '+(c['trim'] or 'ללא ציון במאגר')+' מתוך משרד התחבורה.',editorial=editorial().get(c['id']),noindex=bool(c['identity_conflict']) or c['id'] not in editorial())
 @app.get('/compare')
 def compare():
  ids=list(dict.fromkeys(request.args.get('ids','').split(',')))
  if len(ids)>3:raise InvalidFilter('אפשר להשוות עד שלושה רכבים')
  cars=[]
  for cid in ids:
   if cid:
    r=db().execute('SELECT * FROM cars WHERE id=?',(cid,)).fetchone()
    if not r or r['active_count'] is None or r['active_count']<=MIN_ACTIVE:abort(404)
    cars.append(public_car(r))
  return render_template('compare.html',cars=cars,profiles=[vehicle_profile(db(),c,json.loads(db().execute('SELECT raw_json FROM cars WHERE id=?',(c['id'],)).fetchone()[0])) for c in cars],stats=summary(),title='השוואת רכבים ברורה',noindex=True)
 @app.get('/sources')
 def sources():
  path=ROOT/'data/download-manifest.json';data=json.loads(path.read_text()) if path.exists() else {'sources':[]}
  foreign=json.loads((ROOT/'data/foreign-manifest.json').read_text()) if (ROOT/'data/foreign-manifest.json').exists() else []
  return render_template('sources.html',stats=summary(),sources=data['sources'],foreign=foreign,title='מקורות, כיסוי ושיטת ההשוואה',description='מאיפה מגיעים נתוני הרכב, מה חסר ומה משמעות כל נתון.')
 @app.get('/guides/<slug>')
 def guide(slug):
  titles={'child-seats':'איך בודקים מקום למושבי בטיחות','fuel':'איך משווים דלק, חשמל ועלויות נסיעה','prices':'איזה מחיר אתם רואים כאן'}
  if slug not in titles:abort(404)
  return render_template('guide.html',slug=slug,title=titles[slug],description=titles[slug])
 @app.get('/api/cars')
 def api_cars():
  cars,total,f=search(request.args);return jsonify(cars=cars,total=total,page=f['page'],page_size=18,filters=f)
 @app.get('/api/stats')
 def api_stats():return jsonify(summary())
 @app.get('/market')
 @app.get('/api/rankings')
 def rankings():
  year=validated_int(request.args,'year',2025,1996,2026)
  if year is None:raise InvalidFilter('נדרשת שנה לדירוג')
  body=request.args.get('body','')
  if body not in ['', 'פנאי-שטח', "הצ'בק", 'סדאן', 'סטיישן', 'MPV', 'קופה', 'קבריולט', 'קומבי', 'ואן/נוסעים']:raise InvalidFilter('סוג מרכב לא תקין')
  where='WHERE year=? AND kind=\'P\' AND active_count>?'
  values=[year,MIN_ACTIVE]
  if body:where+=' AND body=?';values.append(body)
  rows=[dict(r) for r in db().execute('SELECT make,model,body,SUM(active_count) total,COUNT(*) variants FROM cars '+where+' GROUP BY make,model,body ORDER BY total DESC,make,model LIMIT 15',values)]
  if request.path.startswith('/api/'):
   return jsonify(metric='active_registered_stock',year=year,body=body,minimum_active_exclusive=MIN_ACTIVE,source_fetched_at=summary()['source_fetched_at'],models=rows)
  return render_template('market.html',ranking=rows,year=year,body=body,stats=summary(),title='רכבים נפוצים בישראל — לפי קטגוריה ושנת ייצור')
 @app.get('/health')
 def health():db().execute('SELECT 1 FROM cars LIMIT 1');return jsonify(status='ok')
 @app.get('/robots.txt')
 def robots():return Response('User-agent: *\nDisallow: /api/\nDisallow: /compare\nSitemap: '+app.config['BASE_URL']+'/sitemap.xml\n',mimetype='text/plain')
 @app.get('/sitemap.xml')
 def sitemap_index():
  # Bounded sitemaps; facet permutations are never generated.
  n=len(editorial())
  paths=['/sitemap-pages.xml']+['/sitemap-cars-'+str(i)+'.xml' for i in range((n+9999)//10000)]
  text='<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<sitemap><loc>'+html.escape(app.config['BASE_URL']+p)+'</loc></sitemap>' for p in paths)+'</sitemapindex>'
  return Response(text,mimetype='application/xml')
 @app.get('/sitemap-pages.xml')
 @app.get('/sitemap-cars-<int:part>.xml')
 def sitemap(part=None):
  if part is None:paths=['/','/cars','/sources']+['/guides/'+s for s in ['child-seats','fuel','prices']]
  else:
   if part<0 or part>100:abort(404)
   paths=['/cars/'+cid for cid in sorted(editorial())[part*10000:(part+1)*10000]]
   if not paths:abort(404)
  return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+html.escape(app.config['BASE_URL']+p)+'</loc></url>' for p in paths)+'</urlset>',mimetype='application/xml')
 return app
