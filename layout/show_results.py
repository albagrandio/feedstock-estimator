"""Results page: per-module tables, Excel download and the interactive map."""

import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.excel_export import build_excel
from src.maps import build_map


def _onclick_edit():
    st.session_state.show_results = False


def _combined_tables() -> dict:
    """Flatten every module's tables into one ordered dict for the Excel export,
    prefixing sheet names with the module label."""
    combined = {}
    labels = st.session_state.get("module_labels", {})
    for module, result in st.session_state.get("results", {}).items():
        short = labels.get(module, module).split("—")[0].strip()[:12]
        for name, df in result.tables.items():
            combined[f"{short} {name}"] = df
    return combined


def _render_map(result, sites):
    gdf_iso = result.gdf_isochrones
    if gdf_iso is None or gdf_iso.empty:
        st.info("No isochrones available for this module.")
        return

    rings = list(gdf_iso["isochrone"].unique())
    cols = st.columns([2, 1, 1])
    with cols[0]:
        chosen = st.multiselect("Isochrones to show", rings, default=rings, key=f"rings_{id(result)}")
    with cols[1]:
        show_comp = st.toggle("Competitors", value=True, key=f"comp_{id(result)}")
    with cols[2]:
        show_overlap = st.toggle("Overlaps", value=True, key=f"ovl_{id(result)}")

    shown = gdf_iso[gdf_iso["isochrone"].isin(chosen)] if chosen else gdf_iso
    shown = gpd.GeoDataFrame(shown, geometry="geometry", crs="EPSG:4326")

    m = build_map(
        gdf_isochrones=shown,
        gdf_parcels=result.gdf_parcels,
        competitors=result.competitors,
        show_competitors=show_comp,
        show_overlap=show_overlap,
        sites=sites,
    )
    st_folium(m, use_container_width=True, height=560, returned_objects=[])


def show_results():
    sites = st.session_state.get("sites", [])
    country = st.session_state.get("country", "")
    results = st.session_state.get("results", {})
    errors = st.session_state.get("errors", {})
    labels = st.session_state.get("module_labels", {})

    top = st.columns([3, 1])
    with top[0]:
        st.subheader("Estimation results")
        site_names = ", ".join(s["name"] for s in sites) if sites else "—"
        st.write(f"**{country.capitalize()}** · {len(sites)} site(s): {site_names}")
    with top[1]:
        st.button("← Edit inputs", on_click=_onclick_edit)

    # Excel download for everything that ran.
    combined = _combined_tables()
    if combined:
        st.download_button(
            "⬇ Download Excel",
            data=build_excel(combined),
            file_name="cr_nr_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    for module, msg in errors.items():
        st.warning(f"**{labels.get(module, module)}** — {msg}")

    if not results:
        st.info("No module produced results. Adjust the inputs and try again.")
        return

    for module, result in results.items():
        st.markdown("---")
        st.markdown(f"### {labels.get(module, module)}")

        if result.summary:
            metric_cols = st.columns(min(len(result.summary), 4))
            for i, (k, v) in enumerate(result.summary.items()):
                metric_cols[i % len(metric_cols)].metric(k, v)

        tab_tables, tab_map = st.tabs(["Tables", "Map"])
        with tab_tables:
            for name, df in result.tables.items():
                with st.expander(name, expanded=(name == next(iter(result.tables)))):
                    show_index = df.index.name is not None or not isinstance(df.index, pd.RangeIndex)
                    st.dataframe(df, use_container_width=True, hide_index=not show_index)
        with tab_map:
            _render_map(result, sites)
