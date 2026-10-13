import json
import pathlib
import sqlite3
import sys
import pytest
from app import create_app
from app.insights import photos, present_car, vehicle_profile

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    return create_app({'TESTING': True}).test_client()


def test_catalog_enforces_registered_stock_threshold(client):
    response = client.get('/api/cars?year_min=')
    assert response.status_code == 200
    cars = response.get_json()['cars']
    assert cars and all(c['active_count'] > 10 for c in cars)
    with sqlite3.connect(ROOT/'data/catalog.sqlite') as db:
        excluded = db.execute('SELECT id FROM cars WHERE active_count<=10 LIMIT 1').fetchone()[0]
    assert client.get('/cars/'+excluded).status_code == 404
    assert client.get('/compare?ids='+excluded).status_code == 404


def test_price_body_power_filters_match_the_requested_interval(client):
    j = client.get('/api/cars?body=פנאי-שטח&budget_min=150000&budget=200000&power_min=150').get_json()
    assert j['total'] > 0
    assert all(c['body']=='פנאי-שטח' and 150000<=c['price']<=200000 and c['power_hp']>=150 for c in j['cars'])


@pytest.mark.parametrize('query', ['body=unknown', 'budget_min=200000&budget=100000', 'power_min=-1'])
def test_new_filters_reject_invalid_inputs(client, query):
    assert client.get('/api/cars?'+query).status_code == 400


def test_rankings_are_current_registered_stock_not_sales(client):
    j = client.get('/api/rankings?year=2025&body=סדאן').get_json()
    assert j['metric']=='active_registered_stock' and j['year']==2025
    assert j['models'] and all(r['body']=='סדאן' and r['total']>10 for r in j['models'])
    with sqlite3.connect(ROOT/'data/catalog.sqlite') as db:
        top = j['models'][0]
        count = db.execute('SELECT SUM(active_count) FROM cars WHERE make=? AND model=? AND body=? AND kind=? AND year=? AND active_count>10',
                           (top['make'],top['model'],top['body'],'P',2025)).fetchone()[0]
    assert top['total']==count
    assert client.get('/api/rankings?year=1800').status_code==400


def test_missing_measurements_are_not_zero_or_ratings():
    with sqlite3.connect('file:'+str(ROOT/'data/catalog.sqlite')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT * FROM cars WHERE id=?',('545507f621fd1c48',)).fetchone()
        profile=vehicle_profile(db,present_car(row),json.loads(row['raw_json']))
    assert next(m for m in profile['metrics'] if m['key']=='co2_wltp')['value'] is None
    assert profile['country']=='סין'
    assert next(s for s in profile['safety'] if s['key']=='bakarat_shyut_adaptivit_ind')['value']==1
    assert next(d for d in profile['dimensions'] if d['label']=='גרירה עם בלמים')['value'] is None


def test_photos_have_files_attribution_and_narrow_model_scope(client):
    for p in photos():
        assert (ROOT/'app/static'/p['file']).is_file()
        assert p['author'] and p['license_url'].startswith('https://') and p['source_url'].startswith('https://')
    with sqlite3.connect(ROOT/'data/catalog.sqlite') as db:
        db.row_factory=sqlite3.Row
        photo_car=present_car(db.execute('SELECT * FROM cars WHERE id=?',('73df2cd7998bd1ea',)).fetchone())
        no_photo=present_car(db.execute('SELECT * FROM cars WHERE id=?',('545507f621fd1c48',)).fetchone())
    assert photo_car['photo'] and no_photo['photo'] is None
    body=client.get('/cars/73df2cd7998bd1ea').data
    assert b'bmw_i4_m50.png' in body and b'CC BY-SA 4.0' in body


def test_product_exposes_safety_price_context_and_scenario_without_fabricated_prices(client):
    body=client.get('/cars/545507f621fd1c48').data.decode()
    assert 'בקרת שיוט אדפטיבית' in body and 'מחירון לוי יצחק' in body
    assert 'טרם חובר מקור מורשה' in body and 'data-electric-consumption' in body
    assert 'נוכחות בישראל' in body and 'אין ציון כולל' in body


def test_photo_import_requires_usable_license_and_author():
    sys.path.insert(0,str(ROOT/'scripts'))
    from import_vehicle_photo import license_record
    metadata={'LicenseShortName': {'value': 'CC BY-SA 4.0'}, 'Artist': {'value':'<a>Alice</a>'},
              'LicenseUrl': {'value':'https://creativecommons.org/licenses/by-sa/4.0/'}}
    assert license_record({'extmetadata':metadata})['author']=='Alice'
    for bad in ['All rights reserved','CC BY-NC 4.0','']:
        metadata['LicenseShortName']['value']=bad
        with pytest.raises(ValueError):license_record({'extmetadata':metadata})


def test_cloud_service_url_is_used_for_canonical_links(monkeypatch):
    monkeypatch.delenv('BASE_URL', raising=False)
    monkeypatch.setenv('RENDER_EXTERNAL_URL','https://car-clear-test.example')
    app=create_app({'TESTING':True})
    response=app.test_client().get('/')
    assert b'https://car-clear-test.example/' in response.data
    monkeypatch.setenv('BASE_URL','https://custom-domain.example')
    assert create_app().config['BASE_URL']=='https://custom-domain.example'
