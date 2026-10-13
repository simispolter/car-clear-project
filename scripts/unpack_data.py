"""Extract Drive data bundles and rejoin the large untouched gzip registry.
Usage: python scripts/unpack_data.py /path/to/downloaded/drive/files
Existing different files are not overwritten. Original uncompressed SHA256 is in manifests.
"""
import pathlib,shutil,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1];src=pathlib.Path(sys.argv[1]);dest=root/'data/raw';dest.mkdir(parents=True,exist_ok=True)
for bundle in sorted(src.glob('vehicle-data-*.zip')):
 with zipfile.ZipFile(bundle) as z:
  for entry in z.infolist():
   p=root/entry.filename
   if not p.resolve().is_relative_to(root.resolve()):raise ValueError('Invalid archive path')
   if entry.is_dir():p.mkdir(parents=True,exist_ok=True);continue
   p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists():continue
   with z.open(entry) as a,p.open('wb') as b:shutil.copyfileobj(a,b)
parts=sorted(src.glob('vehicle-registry-full.csv.gz.part*'))
if parts:
 if len(parts)!=3 or [x.name.rsplit('part',1)[1] for x in parts]!=['001','002','003']:raise ValueError('Download all three registry parts')
 target=dest/'053cea08-09bc-40ec-8f7a-156f0677aff3.csv.gz'
 if not target.exists():
  tmp=target.with_suffix('.joining')
  with tmp.open('wb') as out:
   for p in parts:
    with p.open('rb') as f:shutil.copyfileobj(f,out)
  tmp.replace(target)
print('Data files available in',dest)
