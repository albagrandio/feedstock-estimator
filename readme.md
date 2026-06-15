# Verdalia — CR & NR Estimator

Streamlit web app that, given a candidate plant location, estimates feedstock and
hectare availability and computes the **Cover Ratio (CR)** and **Nitrogen Ratio
(NR)** reachable by truck. Sibling of `WebApp/feedstock-estimator`, reusing its
PostgreSQL data layer (`src/backend.py`).

## Status (first vertical slice)

| Country | Feedstock | Hectares | CR | NR |
|---|---|---|---|---|
| **Spain** | stub | stub | stub | ✅ implemented (SIGPAC, parcel-level) |
| **Italy** | stub | stub | stub | stub |

Stubs report exactly which notebook they are ported from (see
`src/pipelines/stubs.py`). Porting source lives in
`examples/nr1-sigpac/cr_nr_analysis/`.

## Architecture

```
app.py                      Streamlit entry point
layout/
  homepage.py               input form (coords, country, modules, options)
  show_results.py           tables, Excel download, interactive map
src/
  pipelines/
    router.py               PipelineInput / PipelineResult contract + routing
    nr_spain.py             ✅ Spain NR pipeline (PostgreSQL SIGPAC)
    stubs.py                placeholders for the remaining routes
  backend.py                PostgreSQL data layer (reused)
  digestate.py              calculate_absorption_lazy + IsochroneCalculator (reused)
  Verdalia_feedstock_class*.py  feedstock calculators (reused)
  excel_export.py           multi-sheet .xlsx builder
  maps.py                   Folium map (iso selector, competitors, overlaps)
```

Every pipeline returns a `PipelineResult` (`tables`, `gdf_isochrones`,
`gdf_parcels`, `competitors`, `summary`, `meta`). Adding a country/module = write
one pipeline function and register it in `router.get_pipeline`.

## Environment variables

Same `.env` as the feedstock-estimator (PostgreSQL + map keys):

```
DATABASE_TYPE=postgresql
DBAPI=psycopg2
USER=...
PASSWORD=...
HOST=...
BING_KEY=...        # Bing Maps (truck isochrones)
MAPBOX_TOKEN=...     # optional, geocoding
```

## Run locally

```sh
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# secrets: either a local .env (USER/PASSWORD/HOST/BING_KEY/...) or .streamlit/secrets.toml
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

The repo is deploy-ready: `app.py` at the root, `requirements.txt`, and a
`.gitignore` that keeps secrets out of git.

1. Push this folder's contents to a GitHub repo:
   ```sh
   git init -b main
   git add .                 # .env / venv / secrets.toml are git-ignored
   git commit -m "CR & NR estimator app"
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main
   ```
2. Go to https://share.streamlit.io → **New app** → pick the repo, branch `main`,
   **Main file path** = `app.py`.
3. In **Settings → Secrets**, paste the keys from `.streamlit/secrets.toml.example`
   with real values. `app.py` bridges `st.secrets` into environment variables, so
   `os.getenv(...)` works without a `.env`.

**Caveat:** the Spain NR pipeline reads the Azure PostgreSQL DB. Streamlit Cloud
runs on the public internet, so that route only works if the DB is reachable from
there (firewall open). The UI, Bing isochrones on the map, Excel export and the
stubs all work regardless — a full visual demo.

## Notes / gotchas

- All isochrones use Bing Maps `travelMode=truck`.
- Metric CRS: Spain `EPSG:25830`, Italy `EPSG:32633`.
- SIGPAC polygons are repaired with `buffer(0)` after reprojection.
- The notebooks read Unity Catalog via Spark; this app does **not** — pipelines
  must use the PostgreSQL layer, as `nr_spain.py` does.
