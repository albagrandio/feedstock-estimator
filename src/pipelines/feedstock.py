"""Feedstock availability (CR numerator) for Spain and Italy.

Reuses the production-proven PostgreSQL path of the feedstock-estimator app:
`PrepGoldView` loads the municipal feedstock GeoDataFrame and
`MunicipalityFeedstockCalculator` scales feedstock tonnage / heads to each truck
isochrone. This is the `df_full_base` / `gdf_isochrones_full` of the CR notebooks,
computed per site.

Note: the per-feedstock selection (dict_rename keys) is not yet applied as a hard
filter — the full tonnage/heads tables are returned. Mapping the dict_rename
categories to the calculator's output rows is country-specific and will be added
once validated against the DB.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.backend import PrepGoldView
from src.pipelines.router import PipelineInput, PipelineResult
from src.Verdalia_feedstock_class import MunicipalityFeedstockCalculator


def run_pipeline(inputs: PipelineInput) -> PipelineResult:
    """Feedstock tonnage + heads reachable per site, per isochrone."""
    if not (inputs.distances or inputs.times):
        raise ValueError("Feedstock availability requires at least one isochrone distance or time.")

    flag = inputs.country  # "spain" | "italy"
    gdf = PrepGoldView(flag).merged_df  # municipal feedstock GeoDataFrame (PostgreSQL)

    tonnage_frames = []
    heads_frames = []
    iso_frames = []
    for site in inputs.effective_sites:
        calc = MunicipalityFeedstockCalculator(
            gdf, site["lon"], site["lat"], inputs.distances, inputs.times, flag=flag
        )
        df_tonnage, df_heads, gdf_iso = calc.calculate_feedstock_tonnage()

        t = df_tonnage.copy()
        t.index.name = "feedstock"
        t = t.reset_index()
        t.insert(0, "site", site["name"])
        tonnage_frames.append(t)

        h = df_heads.copy()
        h.index.name = "feedstock"
        h = h.reset_index()
        h.insert(0, "site", site["name"])
        heads_frames.append(h)

        gi = gpd.GeoDataFrame(gdf_iso, geometry="geometry", crs="EPSG:4326").copy()
        gi["site"] = site["name"]
        iso_frames.append(gi)

    tonnage = pd.concat(tonnage_frames, ignore_index=True)
    heads = pd.concat(heads_frames, ignore_index=True)
    gdf_iso_all = gpd.GeoDataFrame(pd.concat(iso_frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")

    return PipelineResult(
        tables={"Feedstock tonnage (ktn)": tonnage, "Feedstock heads": heads},
        gdf_isochrones=gdf_iso_all,
        gdf_parcels=None,
        summary={
            "Country": flag.capitalize(),
            "Sites": str(len(inputs.effective_sites)),
            "Isochrones": ", ".join(gdf_iso_all["isochrone"].unique()),
        },
        meta={"country": flag, "module": "feedstock"},
    )
