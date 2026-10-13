"""Flask entrypoint for Vercel; the immutable database is cached in /tmp."""
import json
import os
import pathlib
import tempfile

from app import create_app
from scripts.prepare_catalog import restore

database = None
if os.environ.get('VERCEL') == '1':
    import fcntl

    root = pathlib.Path(__file__).resolve().parent
    snapshot = json.loads((root/'data/catalog-snapshot.json').read_text())
    cache = pathlib.Path(tempfile.gettempdir())/'car-clear'/snapshot['sha256'][:16]
    cache.mkdir(parents=True, exist_ok=True)
    database = cache/'catalog.sqlite'
    # Concurrent workers can share a warm instance's temporary filesystem.
    with (cache/'restore.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(database)

app = create_app({'DATABASE': str(database)} if database else None)
