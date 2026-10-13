.PHONY: setup pull catalog run test
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
pull:
	python3 scripts/pull_data.py --extended
catalog:
	python3 scripts/build_catalog.py
run:
	.venv/bin/gunicorn --no-control-socket --bind 0.0.0.0:8000 --workers 2 --threads 4 wsgi:app
test:
	.venv/bin/python -m pytest -q
