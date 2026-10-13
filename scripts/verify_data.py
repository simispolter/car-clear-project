"""Verify original source bytes after Drive download; no parsing or rewriting."""
import gzip,hashlib,json,pathlib,sys
p=pathlib.Path(__file__).resolve().parents[1]/'data/raw';bad=[]
for f in p.glob('*.manifest.json'):
 m=json.loads(f.read_text());target=p/(f.name.replace('.manifest.json','.csv.gz'))
 if not m.get('complete') or not target.exists():continue
 h=hashlib.sha256()
 with gzip.open(target,'rb') as r:
  while b:=r.read(1048576):h.update(b)
 ok=h.hexdigest()==m.get('sha256_uncompressed');print('OK' if ok else 'FAIL',target.name)
 if not ok:bad.append(str(target))
if bad:sys.exit(1)
