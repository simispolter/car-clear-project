FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.pem \
    if [ -f /tmp/build-ca.pem ]; then PIP_CERT=/tmp/build-ca.pem pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY app ./app
COPY wsgi.py .
COPY scripts/prepare_catalog.py ./scripts/prepare_catalog.py
COPY data/catalog.sqlite.gz data/catalog-snapshot.json data/catalog-summary.json data/download-manifest.json data/foreign-manifest.json data/market-sources.json data/vehicle-photos.json data/editorial-pages.json ./data/
RUN python scripts/prepare_catalog.py && rm data/catalog.sqlite.gz
RUN useradd --system --uid 10001 carapp && chown -R carapp:carapp /app
USER carapp
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=2)"
CMD ["sh","-c","exec gunicorn --no-control-socket --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 30 --access-logfile - wsgi:app"]
