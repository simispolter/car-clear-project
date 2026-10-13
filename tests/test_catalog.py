import json,pathlib,sqlite3,sys,urllib.parse
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from app import create_app
from app.web import compile_filters,InvalidFilter
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from build_catalog import key,number,drive_type
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[1]
@pytest.fixture
def client():return create_app({'TESTING':True}).test_client()
def test_key_normalizes_official_numeric_codes():
 assert key({'sug_degem':'P','tozeret_cd':'00928','degem_cd':'01000','shnat_yitzur':'2024'})==('P','928','1000','2024')
def test_null_and_zero_values_are_not_fake_measurements():
 assert number('',True) is None and number('0',True) is None and number('nan') is None
 assert number('0')==0
@pytest.mark.parametrize('path',['/','/cars','/sources','/guides/child-seats','/guides/fuel','/guides/prices','/compare','/robots.txt','/sitemap.xml','/sitemap-pages.xml','/health'])
def test_pages_render_without_errors(client,path):assert client.get(path).status_code==200
def test_real_budget_family_filters(client):
 j=client.get('/api/cars?budget=170000&year_min=2024&children=2&drive=hybrid').get_json()
 assert j['total']>0
 for c in j['cars']:
  assert c['price']<=170000 and c['year']>=2024 and c['seats']>=4 and c['doors']>=4 and c['drive_type']=='hybrid'
  assert 'raw_json' not in c
@pytest.mark.parametrize('query',['budget=-1','budget=x','sort=evil','kind=z','children=8','year_min=1800','page=0','drive=weird'])
def test_invalid_filters_are_400(client,query):assert client.get('/api/cars?'+query).status_code==400
def test_like_wildcards_and_injection_are_literal(client):
 assert client.get('/api/cars?q='+urllib.parse.quote("' OR 1=1 --")).get_json()['total']==0
 assert client.get('/api/cars?q=%25').get_json()['total']==0
 assert client.get('/api/cars?make='+urllib.parse.quote("' OR 1=1 --")).get_json()['total']==0
def test_missing_child_fit_and_consumption_do_not_pass_filters(client):
 assert client.get('/api/cars?fit_only=1&children=2').get_json()['total']==0
 assert client.get('/api/cars?consumption=7').get_json()['total']==0
def test_co2_filter_excludes_ev_and_plugin(client):
 j=client.get('/api/cars?co2=150').get_json();assert j['total']>0
 assert all(c['drive_type'] in ['petrol','diesel','hybrid'] and 0<c['co2_wltp']<=150 for c in j['cars'])
def test_detail_compare_and_unknown(client):
 cars=client.get('/api/cars?year_min=2024').get_json()['cars'][:3]
 for c in cars:assert client.get('/cars/'+c['id']).status_code==200
 p=client.get('/compare?ids='+','.join(c['id'] for c in cars));assert p.status_code==200 and 'צריכת דלק'.encode() in p.data
 assert client.get('/compare?ids=a,b,c,d').status_code==400
 assert client.get('/cars/not-a-real-id').status_code==404
 assert client.get('/compare?ids=not-a-real-id').status_code==404
def test_provenance_join_and_source_coverage():
 d=json.loads((ROOT/'data/catalog-summary.json').read_text())
 assert d['catalog_rows']==d['source_rows'] and d['unmatched_price_keys']==0 and d['price_covered']==d['catalog_rows']
 db=sqlite3.connect(ROOT/'data/catalog.sqlite')
 assert db.execute('SELECT count(*) FROM cars WHERE seats<=0 OR co2_wltp<=0 OR price<=0').fetchone()[0]==0
 assert db.execute('SELECT count(DISTINCT id) FROM cars').fetchone()[0]==d['catalog_rows']
def test_security_and_facet_indexing(client):
 r=client.get('/cars?budget=150000')
 assert b'noindex,follow' in r.data and r.headers['X-Content-Type-Options']=='nosniff'
 assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
 assert b'/api/' in client.get('/robots.txt').data
