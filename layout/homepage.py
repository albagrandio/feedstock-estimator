"""Input page for the CR & NR estimator.

Collects coordinates, country, the modules to run, and per-module options, then
dispatches to the pipeline router. Results are stored in session state and the
results page takes over.
"""

import base64
import os

import streamlit as st

import pandas as pd

import layout.show_results as show_results
from src.feedstock_config import DIET_KEYS, FEEDSTOCK_KEYS, ITALY_CROP_LABEL, load_spain_crops
from src.pipelines import PipelineInput, NotImplementedYet, run
from src.pipelines.router import (
    COUNTRY_ITALY,
    COUNTRY_SPAIN,
    MODULE_CR,
    MODULE_FEEDSTOCK,
    MODULE_HECTARES,
    MODULE_NR,
)
from src.utils import browser_tab_title, validate_coordinates

DISTANCE_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100]
TIME_OPTIONS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]

MODULE_LABELS = {
    MODULE_FEEDSTOCK: "Feedstock availability (CR numerator)",
    MODULE_HECTARES: "Hectare availability (NR numerator)",
    MODULE_CR: "CR — Cover Ratio",
    MODULE_NR: "NR — Nitrogen Ratio",
}


def _header():
    browser_tab_title("Verdalia — CR & NR Estimator")
    logo_html = ""
    logo_path = "assets/verdalia-logo-white.png"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        logo_html = f'<img src="data:image/png;base64,{encoded}" style="height:30px;margin-right:12px;">'

    # Fixed full-width Verdalia bar pinned to the very top (like st_navbar in the
    # reference app), Streamlit's toolbar hidden, and content padded to clear it.
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&display=swap');
            * {{ font-family: 'Lato', sans-serif; }}
            header[data-testid="stHeader"] {{ display: none; }}
            #MainMenu, footer {{ visibility: hidden; }}
            .block-container,
            [data-testid="stMainBlockContainer"],
            [data-testid="stAppViewBlockContainer"] {{
                padding-top: 64px;
                padding-right: 1.5rem;
                padding-left: 1.5rem;
                padding-bottom: 0rem;
                max-width: 100%;
            }}
            .verdalia-header {{
                position: fixed; top: 0; left: 0; right: 0; z-index: 999990;
                height: 48px; padding: 0 20px;
                background-color: #0B3F43;
                display: flex; align-items: center;
            }}
            .verdalia-header span {{
                color: white; font-size: 20px; font-weight: bold;
            }}
        </style>
        <div class="verdalia-header">
            {logo_html}
            <span>Verdalia Data Platform</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _read_coordinates(raw: str):
    """Parse a 'lat, lon' string. Returns (lat, lon) or (None, None)."""
    if not raw or "," not in raw:
        return None, None
    parts = raw.split(",")
    ok, _ = validate_coordinates(parts[0].strip(), parts[1].strip())
    if not ok:
        return None, None
    return float(parts[0].strip()), float(parts[1].strip())


def _num_text_input(label: str, default: float, key: str) -> float:
    """Numeric input rendered as a plain text field (no +/- steppers), so it
    looks identical to the dropdown fields. Falls back to `default` if invalid."""
    raw = st.text_input(label, value=f"{default:g}", key=key)
    try:
        val = float(str(raw).replace(",", "").strip())
        return max(val, 0.0)
    except (ValueError, TypeError):
        st.caption("↳ enter a number")
        return default


def _parse_sites(sites_df) -> list:
    """Turn the sites editor into a list of valid {name, lat, lon} dicts.

    Rows with missing / invalid coordinates are dropped. The per-site diet is
    attached later (one shared plant diet, like the notebook example)."""
    out = []
    for i, row in sites_df.iterrows():
        lat, lon = row.get("lat"), row.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        ok, _ = validate_coordinates(lat, lon)
        if not ok:
            continue
        name = str(row.get("name") or f"Site {i + 1}").strip()
        out.append({"name": name, "lat": float(lat), "lon": float(lon)})
    return out


def estimate_cr_nr():
    _header()

    if st.session_state.get("show_results"):
        show_results.show_results()
        return

    st.title("CR & NR Estimator")
    st.caption(
        "Feedstock and hectare availability, cover ratio (CR) and nitrogen ratio (NR) "
        "reachable by truck from a candidate plant location."
    )

    col_in, col_opt = st.columns([1, 1])

    with col_in:
        st.subheader("Location")
        country_label = st.radio("Country", ["Spain", "Italy"], horizontal=True)
        country = COUNTRY_SPAIN if country_label == "Spain" else COUNTRY_ITALY

        # Candidate sites (the notebook `sites` dict): one row per plant.
        st.markdown("**Candidate sites** (add one row per plant)")
        sites_init = pd.DataFrame([{"name": "Site 1", "lat": 41.0, "lon": -4.0}])
        sites_edited = st.data_editor(
            sites_init,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Site name"),
                "lat": st.column_config.NumberColumn("Latitude", format="%.6f"),
                "lon": st.column_config.NumberColumn("Longitude", format="%.6f"),
            },
            key="sites_editor",
        )
        sites = _parse_sites(sites_edited)
        if sites_edited[["lat", "lon"]].dropna(how="all").shape[0] and not sites:
            st.error("Each site needs a valid latitude and longitude.")

        st.subheader("Isochrones")
        distances = st.multiselect("Distance (km)", DISTANCE_OPTIONS, default=[10, 20])
        times = st.multiselect("Driving time (min)", TIME_OPTIONS, default=[])

    with col_opt:
        st.subheader("Modules")
        modules = []
        # Stable per-module keys + a country-independent default so switching
        # country never resets the checkboxes (that bug hid the sub-options).
        for key, label in MODULE_LABELS.items():
            if st.checkbox(label, value=(key == MODULE_NR), key=f"mod_{key}"):
                modules.append(key)

        # OPT / non-OPT is an ITALY-only choice:
        #   Italy CR : CR_OPT_Calculator           vs CR_Calculator
        #   Italy NR : NR_OPT_Seminativi_Calculator vs NR_Seminativi_Calculator
        # Spain always uses its single notebooks (CR OPT Calculator Spain, NR Sigpac Spain),
        # so no toggle is shown there.
        optimize = False
        if country == COUNTRY_ITALY and any(m in modules for m in (MODULE_CR, MODULE_NR)):
            optimize = st.toggle(
                "Use optimizer (OPT / cvxpy)",
                value=False,
                key="opt",
                help="Italy only — OPT routes to CR OPT Calculator / NR OPT Seminativi.",
            )

        # CR-specific: plant + competitor diet over the 8 diet feedstocks.
        # Each feedstock is in/out of the diet (1/0), as in the notebook `sites` diets.
        diet_plant: dict = {}
        diet_competitors: dict = {}
        if MODULE_CR in modules:
            st.markdown("**CR — diet** (tick the feedstocks in each diet)")
            diet_init = pd.DataFrame(
                {"feedstock": DIET_KEYS, "plant": [True] * len(DIET_KEYS), "competitor": [True] * len(DIET_KEYS)}
            )
            diet_edited = st.data_editor(
                diet_init,
                hide_index=True,
                use_container_width=True,
                disabled=["feedstock"],
                column_config={
                    "plant": st.column_config.CheckboxColumn("Plant diet"),
                    "competitor": st.column_config.CheckboxColumn("Competitor diet"),
                },
                key="diet_editor",
            )
            # Keep only ticked feedstocks, encoded as 1 (matching the notebook diet dict).
            diet_plant = {r["feedstock"]: 1 for _, r in diet_edited.iterrows() if r["plant"]}
            diet_competitors = {r["feedstock"]: 1 for _, r in diet_edited.iterrows() if r["competitor"]}

        # NR-specific.
        n_produced = None
        abs_non_vuln = abs_vuln = None
        if MODULE_NR in modules:
            st.markdown("**NR — nitrogen**")
            # Default N produced (prod_tipo in the notebooks): Italy 184 200, Spain 223 044.
            default_n = 184200.0 if country == COUNTRY_ITALY else 223044.0
            n_produced = _num_text_input("N produced by plant (kg N/year)", default_n, key=f"nprod_{country}")
            if country == COUNTRY_ITALY:
                # no_vuln / vul absorption coefficients (NR Seminativi notebooks: 340 / 170).
                abs_non_vuln = _num_text_input("Absorption — non-vulnerable soil (kg N/ha)", 340.0, key="abs_no_vuln")
                abs_vuln = _num_text_input("Absorption — vulnerable soil (kg N/ha)", 170.0, key="abs_vuln")
            else:
                st.caption("Spain uses crop_mapping doses (RD 47/2022) automatically.")

        # Feedstock availability selection: the dict_rename categories.
        selected_feedstock = []
        if MODULE_FEEDSTOCK in modules:
            selected_feedstock = st.multiselect(
                "Feedstock to include (keys from dict_rename)",
                FEEDSTOCK_KEYS,
                default=FEEDSTOCK_KEYS,
                key="feedstock_sel",
            )

        # Crop selection — NR / hectares (land) side only.
        #   Spain: pick specific crops from crop_mapping.
        #   Italy: a single "Seminativi" (arable land) category, no per-crop pick.
        selected_crops = []
        if any(m in modules for m in (MODULE_HECTARES, MODULE_NR)):
            if country == COUNTRY_SPAIN:
                spain_crops = list(load_spain_crops())
                selected_crops = st.multiselect(
                    "Crops (from crop_mapping) — leave empty for all",
                    spain_crops,
                    default=[],
                    key="crops_sel",
                )
            else:
                st.caption(f"Italy uses **{ITALY_CROP_LABEL}** (arable land) — no per-crop selection.")

    # Attach the shared plant diet to each site (like the notebook `sites` dict).
    for s in sites:
        s["diet"] = dict(diet_plant)

    can_run = bool(sites and modules and (distances or times))
    if st.button("Estimate", disabled=not can_run, type="primary"):
        _run_modules(
            country=country,
            modules=modules,
            sites=sites,
            distances=distances,
            times=times,
            optimize=optimize,
            selected_feedstock=selected_feedstock,
            selected_crops=selected_crops,
            diet_plant=diet_plant,
            diet_competitors=diet_competitors,
            n_produced=n_produced,
            abs_non_vuln=abs_non_vuln,
            abs_vuln=abs_vuln,
        )

    with st.expander("How this app works"):
        st.write(
            """
            - **Spain → NR** is fully implemented (parcel-level SIGPAC, PostgreSQL).
            - Other country/module combinations are stubbed and will report which
              notebook they are ported from.
            - All isochrones use the Bing Maps API with `travelMode=truck`.
            - Metric CRS: Spain `EPSG:25830`, Italy `EPSG:32633`.
            """
        )


def _run_modules(country, modules, sites, distances, times, optimize,
                 selected_feedstock, selected_crops, diet_plant, diet_competitors,
                 n_produced, abs_non_vuln, abs_vuln):
    results = {}
    errors = {}
    for module in modules:
        inputs = PipelineInput(
            country=country,
            module=module,
            sites=[dict(s) for s in sites],
            distances=distances,
            times=times,
            optimize=optimize,
            selected_feedstock=selected_feedstock,
            selected_crops=selected_crops,
            diet_plant=diet_plant,
            diet_competitors=diet_competitors,
            n_produced_kg=n_produced,
            abs_non_vulnerable=abs_non_vuln,
            abs_vulnerable=abs_vuln,
        )
        try:
            with st.spinner(f"Running {MODULE_LABELS[module]}…"):
                results[module] = run(inputs)
        except NotImplementedYet as e:
            errors[module] = str(e)
        except Exception as e:  # surface pipeline failures without crashing the app
            errors[module] = f"Pipeline error: {e}"

    st.session_state.results = results
    st.session_state.errors = errors
    st.session_state.module_labels = MODULE_LABELS
    st.session_state.sites = sites
    st.session_state.country = country
    st.session_state.show_results = True
    st.rerun()
