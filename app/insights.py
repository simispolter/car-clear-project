"""Presentation of source data, without invented market prices or ratings."""
import json
import math
import pathlib
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIN_ACTIVE = 10
BRANDS = {'ב מ וו': 'BMW', 'פורשה': 'PORSCHE', 'בי ווי די': 'BYD', 'טויוטה': 'TOYOTA', 'יונדאי': 'HYUNDAI', 'קיה': 'KIA', 'מזדה': 'MAZDA', 'סקודה': 'ŠKODA', "ג'אקו": 'JAECOO', "צ'רי": 'CHERY', 'גילי': 'GEELY', 'טסלה': 'TESLA', 'סוזוקי': 'SUZUKI', 'ניסאן': 'NISSAN', 'מיצובישי': 'MITSUBISHI', 'פולקסווגן': 'VOLKSWAGEN', 'סיאט': 'SEAT', 'אאודי': 'AUDI', 'פיג׳ו': 'PEUGEOT', 'פיגו': 'PEUGEOT', 'סיטרואן': 'CITROËN', 'רנו': 'RENAULT', 'הונדה': 'HONDA', 'סובארו': 'SUBARU', 'וולוו': 'VOLVO', 'דאציה': 'DACIA', 'אופל': 'OPEL'}
SAFETY = [
    ('blimat_hirum_lifnei_holhei_regel_ofanaim', 'בלימת חירום להולכי רגל ואופניים'),
    ('bakarat_shyut_adaptivit_ind', 'בקרת שיוט אדפטיבית'),
    ('bakarat_stiya_activ_s', 'תיקון סטייה מנתיב'),
    ('zihuy_beshetah_nistar_ind', 'זיהוי בשטח מת'),
    ('matzlemat_reverse_ind', 'מצלמת נסיעה לאחור'),
    ('blima_otomatit_nesia_leahor', 'בלימה אוטומטית בנסיעה לאחור'),
    ('zihuy_tamrurey_tnua_ind', 'זיהוי תמרורים'),
    ('hayshaney_lahatz_avir_batzmigim_ind', 'ניטור לחץ אוויר בצמיגים'),
    ('bakarat_yatzivut_ind', 'בקרת יציבות'),
    ('shlita_automatit_beorot_gvohim_ind', 'שליטה באורות גבוהים'),
    ('zihuy_rechev_do_galgali', 'זיהוי רכב דו־גלגלי'),
    ('bakarat_mehirut_isa', 'סיוע חכם להגבלת מהירות'),
]


def number(value, positive=False):
    try:
        value = float(str(value).strip())
        if not math.isfinite(value) or (positive and value <= 0):
            return None
        return int(value) if value.is_integer() else value
    except (ValueError, TypeError):
        return None


@lru_cache(maxsize=1)
def photos():
    path = ROOT / 'data/vehicle-photos.json'
    return json.loads(path.read_text()) if path.exists() else []


def present_car(row):
    car = dict(row)
    car.pop('raw_json', None)
    car['brand'] = BRANDS.get(car['make'], car['make'])
    car['photo'] = next((p for p in photos() if p.get('approved') is True
                         and p.get('make') == car['make'] and p.get('model') == car['model']
                         and p.get('year_from', 0) <= car['year'] <= p.get('year_to', 0)
                         and p.get('file', '').startswith('vehicles/')
                         and '..' not in p['file'].split('/')
                         and p.get('license') and p.get('source_url')), None)
    return car


def vehicle_profile(db, car, raw):
    """Cohort is the same body and drivetrain, within two production years."""
    cohort = db.execute(
        'SELECT id,price,power_hp,seats,airbags,active_count,co2_wltp FROM cars '
        'WHERE kind=? AND body=? AND drive_type=? AND year BETWEEN ? AND ? AND active_count>?',
        (car['kind'], car['body'], car['drive_type'], car['year']-2, car['year']+2, MIN_ACTIVE)
    ).fetchall()
    metrics = []
    for key, label, unit, lower in [('power_hp', 'הספק מנוע', 'כ״ס', False), ('seats', 'מקומות ישיבה', 'מושבים', False),
                                  ('airbags', 'כריות אוויר', 'כריות', False), ('co2_wltp', 'פליטות WLTP', 'גרם/ק״מ', True)]:
        values = sorted(r[key] for r in cohort if r[key] is not None and r[key] > 0)
        value = car[key]
        if not values or value is None or value <= 0:
            metrics.append(dict(key=key, label=label, unit=unit, value=None, median=None, percentile=None, bar=0))
            continue
        n = len(values)
        median = (values[(n-1)//2] + values[n//2]) / 2
        percentile = round(100 * (sum(v < value for v in values) + sum(v == value for v in values)/2) / n)
        # The bar positions the physical measurement in its observed range, not a score.
        extent = values[-1] - values[0]
        position = round((value-values[0])/extent*100) if extent else 50
        metrics.append(dict(key=key, label=label, unit=unit, value=value, median=median, percentile=percentile,
                            bar=position, minimum=values[0], maximum=values[-1], lower=lower, count=n))
    safety = [dict(key=key, label=label, value=number(raw.get(key)) if str(raw.get(key, '')).strip() in ['0','1'] else None)
              for key,label in SAFETY]
    prices = sorted(r['price'] for r in cohort if r['price'] is not None and r['price'] > 0)
    price_median = (prices[(len(prices)-1)//2] + prices[len(prices)//2])/2 if prices else None
    rank = 1 + sum(r['active_count'] > car['active_count'] for r in cohort)
    variant_total = db.execute('SELECT COUNT(*) FROM cars WHERE make=? AND model=? AND active_count>?', (car['make'],car['model'],MIN_ACTIVE)).fetchone()[0]
    variants = [present_car(r) for r in db.execute(
        'SELECT * FROM cars WHERE make=? AND model=? AND active_count>? ORDER BY year DESC,active_count DESC LIMIT 18',
        (car['make'],car['model'],MIN_ACTIVE))]
    alternatives = [present_car(r) for r in db.execute(
        'SELECT * FROM cars WHERE kind=? AND body=? AND make!=? AND year BETWEEN ? AND ? '
        'AND active_count>? ORDER BY ABS(COALESCE(price,0)-?),active_count DESC LIMIT 3',
        (car['kind'],car['body'],car['make'],car['year']-1,car['year']+1,MIN_ACTIVE,car['price'] or 0))]
    dimensions = [dict(label=label, value=number(raw.get(key),True), unit=unit) for key,label,unit in [
        ('mishkal_kolel','משקל כולל מותר','ק״ג'), ('gova','גובה רשום','ס״מ'),
        ('kosher_grira_im_blamim','גרירה עם בלמים','ק״ג'), ('kosher_grira_bli_blamim','גרירה ללא בלמים','ק״ג')]]
    return dict(metrics=metrics, cohort_count=len(cohort), safety=safety,
                safety_known=sum(s['value'] is not None for s in safety), safety_present=sum(s['value']==1 for s in safety),
                dimensions=dimensions, price_median=price_median, price_count=len(prices),
                price_delta=round((car['price']/price_median-1)*100) if car['price'] and price_median else None,
                registry_rank=rank, variants=variants, variant_total=variant_total, alternatives=alternatives,
                country=raw.get('tozeret_eretz_nm') or None, axle=raw.get('hanaa_nm') or None,
                battery_voltage=number(raw.get('dg_metach_solela'),True))
