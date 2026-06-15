"""Interactive Folium map for CR & NR results.

Builds the notebook-equivalent map with three extra controls:
  - isochrone selector: which ring(s) to draw (handled by the caller passing a
    filtered `gdf_isochrones`),
  - competitors toggle: show / hide competitor plants,
  - overlap shading: highlight the area intersected by 2+ isochrones of
    different sites (internal competition).

All geometries are expected in EPSG:4326. The function returns a `folium.Map`
to be rendered with `streamlit_folium.st_folium`.
"""

from __future__ import annotations

from typing import Optional

import folium
import geopandas as gpd
from shapely.ops import unary_union

# Distinct ring colours, cycled by isochrone order.
_RING_COLORS = ["#005358", "#0B8A8F", "#3FA796", "#7CC6A6", "#B8E0C2", "#E0A458", "#C25B3F"]


def _center(gdf: gpd.GeoDataFrame):
    b = gdf.total_bounds  # minx, miny, maxx, maxy
    return [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]


def build_map(
    gdf_isochrones: gpd.GeoDataFrame,
    gdf_parcels: Optional[gpd.GeoDataFrame] = None,
    competitors: Optional[gpd.GeoDataFrame] = None,
    show_competitors: bool = True,
    show_overlap: bool = True,
    parcel_color_col: Optional[str] = "Product_name",
    sites: Optional[list] = None,
) -> folium.Map:
    """Assemble the Folium map. `gdf_isochrones` should already be filtered to
    the rings the user selected. `sites` is a list of {name, lat, lon} dicts
    drawn as candidate-plant markers."""
    center = _center(gdf_isochrones)
    m = folium.Map(location=center, zoom_start=10, tiles="cartodbpositron")

    # Parcel / municipality polygons (drawn first, underneath the rings).
    if gdf_parcels is not None and not gdf_parcels.empty:
        parcels_fg = folium.FeatureGroup(name="Parcels", show=True)
        tooltip_fields = [c for c in [parcel_color_col, "covered_ha", "n_absorbable_kg"] if c in gdf_parcels.columns]
        folium.GeoJson(
            gdf_parcels.to_json(),
            style_function=lambda _f: {"fillColor": "#2E7D32", "color": "#2E7D32", "weight": 0.3, "fillOpacity": 0.35},
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields) if tooltip_fields else None,
        ).add_to(parcels_fg)
        parcels_fg.add_to(m)

    # Isochrone rings, one colour per ring.
    rings = list(gdf_isochrones["isochrone"].unique())
    for i, ring in enumerate(rings):
        color = _RING_COLORS[i % len(_RING_COLORS)]
        ring_gdf = gdf_isochrones[gdf_isochrones["isochrone"] == ring]
        fg = folium.FeatureGroup(name=f"Isochrone {ring}", show=True)
        folium.GeoJson(
            ring_gdf.to_json(),
            style_function=lambda _f, c=color: {"fillColor": c, "color": c, "weight": 2, "fillOpacity": 0.15},
            tooltip=f"Isochrone {ring}",
        ).add_to(fg)
        fg.add_to(m)

    # Overlap between isochrones of different sites (internal competition).
    if show_overlap and "site" in gdf_isochrones.columns and gdf_isochrones["site"].nunique() > 1:
        overlap_geom = _pairwise_overlap(gdf_isochrones)
        if overlap_geom is not None and not overlap_geom.is_empty:
            fg = folium.FeatureGroup(name="Overlap (competition)", show=True)
            folium.GeoJson(
                gpd.GeoSeries([overlap_geom], crs="EPSG:4326").to_json(),
                style_function=lambda _f: {"fillColor": "#C0392B", "color": "#C0392B", "weight": 1, "fillOpacity": 0.45},
                tooltip="Overlapping reach",
            ).add_to(fg)
            fg.add_to(m)

    # Competitor plants.
    if show_competitors and competitors is not None and not competitors.empty:
        fg = folium.FeatureGroup(name="Competitors", show=True)
        for _, row in competitors.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            folium.Marker(
                location=[geom.y, geom.x],
                icon=folium.Icon(color="red", icon="industry", prefix="fa"),
                tooltip=str(row.get("name", row.get("plant_id", "competitor"))),
            ).add_to(fg)
        fg.add_to(m)

    # Candidate site markers (one per site).
    for s in sites or []:
        if s.get("lat") is None or s.get("lon") is None:
            continue
        folium.Marker(
            location=[s["lat"], s["lon"]],
            icon=folium.Icon(color="green", icon="star", prefix="fa"),
            tooltip=s.get("name", "Candidate site"),
        ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def _pairwise_overlap(gdf_isochrones: gpd.GeoDataFrame):
    """Union of all pairwise intersections between different sites' rings."""
    sites = list(gdf_isochrones["site"].unique())
    per_site = {s: unary_union(gdf_isochrones[gdf_isochrones["site"] == s].geometry.values) for s in sites}
    inters = []
    for i in range(len(sites)):
        for j in range(i + 1, len(sites)):
            inter = per_site[sites[i]].intersection(per_site[sites[j]])
            if inter and not inter.is_empty:
                inters.append(inter)
    if not inters:
        return None
    return unary_union(inters)
