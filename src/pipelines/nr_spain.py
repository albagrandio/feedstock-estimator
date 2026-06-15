"""Spain NR (SIGPAC) pipeline — the fully implemented vertical slice.

Parcel-level nitrogen absorbable within each truck isochrone, computed from
PostgreSQL SIGPAC data (no Spark / Unity Catalog). This mirrors the
`NR1 Sigpac Spain` notebook but uses the app's existing PostgreSQL data layer:

  1. `PrepDigestateView` pulls the SIGPAC parcels whose municipalities fall in
     the largest isochrone (province + municipality filter) as a Polars LazyFrame.
  2. `calculate_absorption_lazy` joins `crop_mapping_spain.csv` and derives the
     max N dose per parcel (RD 47/2022 logic: slope, irrigation, NVZ).
  3. Parcels become a GeoDataFrame, reprojected to EPSG:25830 for areas.
  4. For each requested distance we clip parcels to the isochrone ring and
     compute covered hectares and N absorbable (covered_ha x dose).
  5. Outputs: pivot of hectares per crop x distance, N summary per distance,
     per-crop N breakdown, and (if N produced is given) the NR ratio.

Reused as-is from the feedstock-estimator src: `PrepDigestateView`,
`calculate_absorption_lazy`, `crop_mapping_spain.csv`, `utils.calculate_isochrones`.
"""

from __future__ import annotations

import os

import geopandas as gpd
import numpy as np
import pandas as pd
import polars as pl
import streamlit as st
from shapely.wkt import loads as wkt_loads

from src.backend import PrepDigestateView
from src.constants import SHAPEFILE_SPAIN, SIGPAC
from src.digestate import calculate_absorption_lazy
from src.pipelines.router import PipelineInput, PipelineResult
from src.utils import calculate_isochrones

# Crop mapping schema (matches feedstock_estimator.digestate_estimator).
_SCHEMA_SPAIN = {
    "Product_id": pl.Float64,
    "Product_name": pl.Utf8,
    "Slope Theshold": pl.Int64,
    "Irrigated": pl.Int64,
    "Dry": pl.Int64,
    "Vulnerable": pl.Int64,
    "Dosis Max N": pl.Float64,
}

_CROP_MAPPING_PATH = "assets/crop_mapping_spain.csv"
_DOSE_COL = "Dosis Maxima N"  # output column of calculate_absorption_lazy


def _load_parcels(latitude: float, longitude: float, max_distance_km: float) -> pd.DataFrame:
    """Pull SIGPAC parcels within the largest isochrone as a pandas DataFrame
    with a max-N dose column already attached."""
    # PrepDigestateView reads st.session_state.flag inside process_sigpac_data.
    st.session_state.flag = "spain"

    digestate_view = PrepDigestateView(
        lat=latitude,
        lon=longitude,
        shapefile=SHAPEFILE_SPAIN,
        sigpac=SIGPAC,
        mun_code="mun_code",
    )
    # The candidate-parcel pull uses a single isochrone; size it to the
    # furthest requested ring so every ring's parcels are covered.
    digestate_view.distance_km = int(max_distance_km)
    gdf_dig: pl.LazyFrame = digestate_view.process_sigpac_data()

    crop_map = pl.scan_csv(
        _CROP_MAPPING_PATH,
        dtypes=_SCHEMA_SPAIN,
        null_values=["#N/A"],
        separator=",",
    )

    lazy_result = calculate_absorption_lazy(gdf_dig, crop_map)
    lazy_result = lazy_result.join(
        crop_map.select(["Product_id", "Product_name"]),
        left_on="par_produc",
        right_on="Product_id",
        how="left",
    )
    return lazy_result.collect().to_pandas()


def _to_metric_gdf(parcels: pd.DataFrame, metric_crs: str) -> gpd.GeoDataFrame:
    """Build a valid metric-CRS GeoDataFrame from the parcel WKT geometries."""
    parcels = parcels.copy()
    parcels["geometry"] = parcels["geometry_wkt"].apply(wkt_loads)
    gdf = gpd.GeoDataFrame(parcels, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.to_crs(metric_crs)
    # SIGPAC polygons often self-intersect; buffer(0) repairs topology.
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    return gdf


def _site_detail(site: dict, distances, metric_crs, selected_crops) -> tuple:
    """Run one site: returns (detail_df rows, gdf_iso rows) for that site."""
    name = site.get("name", "Site")
    lat, lon = site["lat"], site["lon"]
    max_distance = distances[-1]

    parcels = _load_parcels(lat, lon, max_distance)
    gdf_parcels = _to_metric_gdf(parcels, metric_crs)
    if selected_crops:
        gdf_parcels = gdf_parcels[gdf_parcels["Product_name"].isin(selected_crops)]

    gdf_iso = calculate_isochrones(lon, lat, distances=distances, times=[])
    gdf_iso["site"] = name
    gdf_iso = gpd.GeoDataFrame(gdf_iso, geometry="geometry", crs="EPSG:4326")

    rows = []
    for _, iso_row in gdf_iso.iterrows():
        ring = iso_row["isochrone"]
        iso_metric = gpd.GeoDataFrame(geometry=[iso_row["geometry"]], crs="EPSG:4326").to_crs(metric_crs)
        clipped = gpd.clip(gdf_parcels, iso_metric)
        if clipped.empty:
            continue
        clipped = clipped.copy()
        clipped["covered_ha"] = clipped.geometry.area / 1e4
        clipped["n_absorbable_kg"] = clipped["covered_ha"] * clipped[_DOSE_COL].fillna(0.0)
        clipped["isochrone"] = ring
        clipped["site"] = name
        rows.append(
            clipped[["site", "isochrone", "par_produc", "Product_name", "covered_ha", _DOSE_COL, "n_absorbable_kg"]]
        )
    return rows, gdf_iso


def run_pipeline(inputs: PipelineInput) -> PipelineResult:
    """Run the Spain NR SIGPAC pipeline over one or more sites. See module docstring."""
    if not inputs.distances:
        raise ValueError("Spain NR requires at least one isochrone distance (km).")
    if not os.getenv("BING_KEY"):
        raise EnvironmentError("BING_KEY is not set — cannot call the Bing isochrone API.")

    distances = sorted(float(d) for d in inputs.distances)
    max_distance = distances[-1]
    sites = inputs.effective_sites

    # Run every site, accumulating per-parcel detail and isochrone rings.
    detail_rows = []
    iso_frames = []
    for site in sites:
        rows, gdf_iso = _site_detail(site, distances, inputs.metric_crs, inputs.selected_crops)
        detail_rows.extend(rows)
        iso_frames.append(gdf_iso)

    gdf_iso_all = gpd.GeoDataFrame(pd.concat(iso_frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")

    if not detail_rows:
        empty = pd.DataFrame(columns=["site", "isochrone", "Product_name", "covered_ha", "n_absorbable_kg"])
        return PipelineResult(
            tables={"NR detail": empty},
            gdf_isochrones=gdf_iso_all,
            gdf_parcels=None,
            summary={"Result": "No SIGPAC parcels found inside the requested isochrones."},
            meta={"country": "spain", "module": "nr", "optimize": str(inputs.optimize)},
        )

    detail_df = pd.concat(detail_rows, ignore_index=True)
    detail_df["covered_ha"] = detail_df["covered_ha"].round(2)
    detail_df["n_absorbable_kg"] = detail_df["n_absorbable_kg"].round(1)

    # 5a. Hectares per crop x distance (per site).
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

    # 5b. N summary per site x distance.
    n_summary = (
        detail_df.groupby(["site", "isochrone"], as_index=False)
        .agg(ha_total=("covered_ha", "sum"), n_absorbable_kg=("n_absorbable_kg", "sum"))
    )
    n_summary["ha_total"] = n_summary["ha_total"].round(1)
    n_summary["n_absorbable_t"] = (n_summary["n_absorbable_kg"] / 1000).round(1)
    n_summary["n_absorbable_kg"] = n_summary["n_absorbable_kg"].round(0).astype(int)

    # 5c. Per-crop N breakdown.
    n_by_crop = (
        detail_df.groupby(["site", "isochrone", "par_produc", "Product_name"], as_index=False, dropna=False)
        .agg(covered_ha=("covered_ha", "sum"), n_absorbable_kg=("n_absorbable_kg", "sum"))
        .sort_values(["site", "isochrone", "n_absorbable_kg"], ascending=[True, True, False])
        .reset_index(drop=True)
    )
    n_by_crop["covered_ha"] = n_by_crop["covered_ha"].round(2)
    n_by_crop["n_absorbable_kg"] = n_by_crop["n_absorbable_kg"].round(0).astype(int)

    tables = {
        "NR summary": n_summary,
        "Hectares by crop": pivot_ha,
        "N by crop": n_by_crop,
        "NR detail": detail_df,
    }

    summary = {
        "Sites": str(len(sites)),
        "Furthest ring": f"{int(max_distance)} km",
        "Total hectares (furthest ring)": f"{n_summary['ha_total'].max():,.1f} ha",
        "Max N absorbable": f"{n_summary['n_absorbable_kg'].max():,} kg",
    }

    # 5d. NR ratio if the user provided the plant's N production (per site x ring).
    if inputs.n_produced_kg:
        nr_df = n_summary[["site", "isochrone", "n_absorbable_kg"]].copy()
        nr_df["n_produced_kg"] = float(inputs.n_produced_kg)
        nr_df["NR"] = (nr_df["n_absorbable_kg"] / float(inputs.n_produced_kg)).round(2)
        tables["NR ratio"] = nr_df
        summary["N produced (input)"] = f"{float(inputs.n_produced_kg):,.0f} kg"
        summary["Max NR"] = f"{nr_df['NR'].max():.2f}"

    # The full SIGPAC pull can be 100k+ polygons — far too many to draw in Folium.
    # The map shows isochrone rings, competitors and overlaps; a parcel choropleth
    # can be added later with a cap / simplification if needed.
    return PipelineResult(
        tables=tables,
        gdf_isochrones=gdf_iso_all,
        gdf_parcels=None,
        summary=summary,
        meta={"country": "spain", "module": "nr", "optimize": str(inputs.optimize)},
    )
