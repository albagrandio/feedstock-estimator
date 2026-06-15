"""Pipeline contract and routing.

The app lets the user pick a country (Spain / Italy) and one or more modules
(feedstock availability, hectare availability, CR, NR). Each (country, module,
optimize) combination resolves to a single pipeline function via `get_pipeline`.

Data layer: all pipelines read from PostgreSQL through `src.backend`
(`PrepGoldView` / `PrepDigestateView`) — the same layer the feedstock-estimator
app uses. None of them touch Databricks / Unity Catalog or Spark.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import geopandas as gpd
import pandas as pd


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #

# Module keys used across the app
MODULE_FEEDSTOCK = "feedstock"   # feedstock availability (CR numerator, no ratio)
MODULE_HECTARES = "hectares"     # hectare availability (NR numerator, no ratio)
MODULE_CR = "cr"                 # cover ratio
MODULE_NR = "nr"                 # nitrogen ratio

COUNTRY_SPAIN = "spain"
COUNTRY_ITALY = "italy"


class NotImplementedYet(Exception):
    """Raised by stub pipelines that are not part of the first vertical slice."""


@dataclass
class PipelineInput:
    """Everything a pipeline needs to run.

    Attributes:
        country: "spain" or "italy".
        module: one of MODULE_* constants.
        latitude / longitude: candidate plant coordinates (EPSG:4326).
        site_name: label for the candidate site (used in tables / maps).
        distances: list of isochrone ring distances in km.
        times: list of isochrone ring times in minutes (optional).
        optimize: whether to run the cvxpy-based competition allocator (OPT).
        selected_feedstock: feedstock dictionary keys the user wants to include.
        selected_crops: SIGPAC crop codes / names the user wants to include.
        diet_plant: plant diet (feedstock -> share / tonnage) for CR.
        diet_competitors: competitor diet for CR.
        n_produced_kg: nitrogen produced by the plant per year (NR denominator).
        abs_non_vulnerable / abs_vulnerable: Italy-only N absorption coefficients
            (kg N/ha). Spain uses crop_mapping doses automatically.
    """

    country: str
    module: str
    # Candidate sites: [{"name": str, "lat": float, "lon": float, "diet": {feedstock: 1}}].
    # The notebook `sites` dict; supports internal competition / overlap between sites.
    sites: List[Dict] = field(default_factory=list)
    # Single-site convenience (mirrors the first site; kept for simple call sites).
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    site_name: str = "Candidate site"
    distances: List[float] = field(default_factory=list)
    times: List[float] = field(default_factory=list)
    optimize: bool = False
    selected_feedstock: List[str] = field(default_factory=list)
    selected_crops: List[str] = field(default_factory=list)
    diet_plant: Dict[str, float] = field(default_factory=dict)
    diet_competitors: Dict[str, float] = field(default_factory=dict)
    n_produced_kg: Optional[float] = None
    abs_non_vulnerable: Optional[float] = None
    abs_vulnerable: Optional[float] = None

    def __post_init__(self):
        # Keep `sites` and the single-site fields in sync.
        if not self.sites and self.latitude is not None and self.longitude is not None:
            self.sites = [
                {"name": self.site_name, "lat": self.latitude, "lon": self.longitude, "diet": dict(self.diet_plant)}
            ]
        elif self.sites and self.latitude is None:
            first = self.sites[0]
            self.latitude, self.longitude, self.site_name = first["lat"], first["lon"], first.get("name", "Site 1")

    @property
    def effective_sites(self) -> List[Dict]:
        """Always returns a non-empty site list (falls back to the scalar coords)."""
        if self.sites:
            return self.sites
        return [{"name": self.site_name, "lat": self.latitude, "lon": self.longitude, "diet": dict(self.diet_plant)}]

    @property
    def metric_crs(self) -> str:
        """Metric CRS used for area / intersection calculations."""
        return "EPSG:25830" if self.country == COUNTRY_SPAIN else "EPSG:32633"


@dataclass
class PipelineResult:
    """Standard output every pipeline returns.

    Attributes:
        tables: ordered mapping of sheet name -> DataFrame. Drives both the
            on-screen results and the multi-sheet Excel export (sheet names and
            order are preserved).
        gdf_isochrones: isochrone rings (columns: site, isochrone, geometry).
        gdf_parcels: optional parcel / municipality polygons for the map overlay.
        competitors: optional competitor plant points for the map.
        summary: headline metrics shown above the tables.
        meta: echo of the routing decision plus any extra info.
    """

    tables: Dict[str, pd.DataFrame] = field(default_factory=dict)
    gdf_isochrones: Optional[gpd.GeoDataFrame] = None
    gdf_parcels: Optional[gpd.GeoDataFrame] = None
    competitors: Optional[gpd.GeoDataFrame] = None
    summary: Dict[str, str] = field(default_factory=dict)
    meta: Dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #

def get_pipeline(country: str, module: str) -> Callable[[PipelineInput], PipelineResult]:
    """Resolve the pipeline function for a (country, module) pair.

    Imports are local so that a missing optional dependency in a stub path does
    not break the working slice.
    """
    country = country.lower()
    module = module.lower()

    if country == COUNTRY_SPAIN and module == MODULE_NR:
        from src.pipelines.nr_spain import run_pipeline
        return run_pipeline

    # Everything else is stubbed for this first slice.
    from src.pipelines import stubs

    registry: Dict[tuple, Callable] = {
        (COUNTRY_SPAIN, MODULE_FEEDSTOCK): stubs.feedstock_spain,
        (COUNTRY_SPAIN, MODULE_HECTARES): stubs.hectares_spain,
        (COUNTRY_SPAIN, MODULE_CR): stubs.cr_spain,
        (COUNTRY_ITALY, MODULE_FEEDSTOCK): stubs.feedstock_italy,
        (COUNTRY_ITALY, MODULE_HECTARES): stubs.hectares_italy,
        (COUNTRY_ITALY, MODULE_CR): stubs.cr_italy,
        (COUNTRY_ITALY, MODULE_NR): stubs.nr_italy,
    }
    fn = registry.get((country, module))
    if fn is None:
        raise NotImplementedYet(f"No pipeline registered for country={country!r}, module={module!r}.")
    return fn


def run(inputs: PipelineInput) -> PipelineResult:
    """Resolve and execute the right pipeline for the given inputs."""
    pipeline = get_pipeline(inputs.country, inputs.module)
    return pipeline(inputs)
