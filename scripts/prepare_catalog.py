"""Restore the bundled catalog snapshot for a fresh cloud checkout."""
import gzip
import hashlib
import json
import os
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[1]


def restore(destination=None):
    destination = pathlib.Path(destination) if destination else ROOT/'data/catalog.sqlite'
    metadata = json.loads((ROOT/'data/catalog-snapshot.json').read_text())
    if destination.exists():
        # Never overwrite an existing local database as part of deployment setup.
        with sqlite3.connect('file:'+str(destination.resolve())+'?mode=ro',uri=True) as db:
            db.execute('SELECT 1 FROM cars LIMIT 1').fetchone()
        print('Using existing catalog:', destination)
        return
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix('.building')
    digest = hashlib.sha256()
    size = 0
    try:
        with gzip.open(ROOT/'data/catalog.sqlite.gz','rb') as source,temporary.open('xb') as target:
            for chunk in iter(lambda:source.read(1024*1024),b''):
                digest.update(chunk)
                size += len(chunk)
                target.write(chunk)
        if digest.hexdigest()!=metadata['sha256'] or size!=metadata['size_bytes']:
            raise RuntimeError('Catalog snapshot checksum/size mismatch')
        with sqlite3.connect('file:'+str(temporary.resolve())+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                raise RuntimeError('Catalog integrity check failed')
            if db.execute('SELECT COUNT(*) FROM cars').fetchone()[0]!=metadata['catalog_rows']:
                raise RuntimeError('Catalog row count mismatch')
        os.replace(temporary,destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print('Restored verified catalog:',destination)


if __name__=='__main__':
    restore()
