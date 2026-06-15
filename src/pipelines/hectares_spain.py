"""Spain hectare availability (SIGPAC) — the NR numerator without the nitrogen step.

This is the `pivot_results` of the NR1 Sigpac Spain notebook: crop hectares within
each truck isochrone, per site, with no dose / N absorbable. It reuses the exact
per-site SIGPAC pull + clip logic implemented and structured in `nr_spain`, so it
shares the same (PostgreSQL) data path and stays consistent with NR Spain.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.pipelines import nr_spain
from src.pipelines.router import PipelineInput, PipelineResult


def run_pipeline(inputs: PipelineInput) -> PipelineResult:
    """Hectares per crop x distance, per site. See module docstring."""
    if not inputs.distances:
        raise ValueError("Spain hectare availability requires at least one isochrone distance (km).")

    distances = sorted(float(d) for d in inputs.distances)
    max_distance = distances[-1]
    sites = inputs.effective_sites

    detail_rows = []
    iso_frames = []
    for site in sites:
        rows, gdf_iso = nr_spain._site_detail(site, distances, inputs.metric_crs, inputs.selected_crops)
        detail_rows.extend(rows)
        iso_frames.append(gdf_iso)

    gdf_iso_all = gpd.GeoDataFrame(pd.concat(iso_frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")

    if not detail_rows:
        empty = pd.DataFrame(columns=["site", "isochrone", "Product_name", "covered_ha"])
        return PipelineResult(
            tables={"Hectares detail": empty},
            gdf_isochrones=gdf_iso_all,
            gdf_parcels=None,
            summary={"Result": "No SIGPAC parcels found inside the requested isochrones."},
            meta={"country": "spain", "module": "hectares"},
        )

    detail_df = pd.concat(detail_rows, ignore_index=True)
    detail_df = detail_df[["site", "isochrone", "par_produc", "Product_name", "covered_ha"]].copy()
    detail_df["covered_ha"] = detail_df["covered_ha"].round(2)

    # pivot_results: hectares per crop x distance, per site.
    pivot_ha = (
        detail_df.groupby(["site", "par_produc", "Product_name", "isochrone"], dropna=False)["covered_ha"]
        .sum()
        .reset_index()
        .pivot_table(
            index=["site", "par_produc", "Product_name"], columns="isochrone", values="covered_ha", aggfunc="sum"
        )
        .round(2)
        .reset_index()
    )

    ha_summary = (
        detail_df.groupby(["site", "isochrone"], as_index=False)["covered_ha"].sum().rename(columns={"covered_ha": "ha_total"})
    )
    ha_summary["ha_total"] = ha_summary["ha_total"].round(1)

    return PipelineResult(
        tables={"Hectares summary": ha_summary, "Hectares by crop": pivot_ha, "Hectares detail": detail_df},
        gdf_isochrones=gdf_iso_all,
        gdf_parcels=None,
        summary={
            "Sites": str(len(sites)),
            "Furthest ring": f"{int(max_distance)} km",
            "Total hectares (furthest ring)": f"{ha_summary['ha_total'].max():,.1f} ha",
        },
        meta={"country": "spain", "module": "hectares"},
    )
