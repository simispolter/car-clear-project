# Validation of the redesign — 2026-10-13

Verified in `/workspace/car-clear-project`, Python 3.12.14, Flask 3.1.3, Gunicorn 26.2.0.

- `python -m pytest -q`: **38 passed**, 1.92 seconds. Covers the original application plus registration threshold, new filters, rejection of invalid input, ranking semantics, missing measurements, photo scope and licenses, and product sections.
- Live Gunicorn: `/health` returned `{"status":"ok"}`; home and product pages rendered; the sedan/budget API query returned 93 matching versions; ranking API returned `active_registered_stock`.
- Chromium / Playwright: home, catalog, product, comparison, registration rankings and sources checked at **320, 390, 768, 1024 and 1440 pixels**. No page-level horizontal overflow. Tables scroll within their containers. No JavaScript page errors.
- Mobile filter dialog: open, edit model and drivetrain, submit and obtain matching results.
- Comparison: enforce three-car maximum, persist selection, navigate to comparison, remove a car, hide and restore identical rows.
- Photo dialog: open and dismiss with Escape.
- Ownership scenarios: fuel, electric and plugin computations exercised with explicitly entered example assumptions. Electric 15,000 km × 18 kWh/100 km × 0.65 NIS/kWh / 12 = 146 NIS/month rounded. Insurance 6,000 NIS/year adds 500 NIS/month. Fuel 6 L/100 km × 8 NIS/L yields 600 NIS/month. A 70% electric/30% fuel split yields 282 NIS/month rounded, before insurance.
- Local font files and four licensed photo families load successfully. Attribution records and source/license links are retained.
- Source SQLite hash matches the uploaded database; no data rebuild was performed.

Screenshots are in `/workspace/car-clear-review`. The new Windows batch launcher was **not executed on Windows**. Docker build was **not run**. The live Commons import operation and the candidate market-source integrations remain **unverified/blocked** by network/data access; missing market measurements are not presented as real prices or trends.

The code is imported into the selected local Git checkout. It has not been pushed to GitHub, deployed as a public website, or copied automatically to the user's Windows machine.
