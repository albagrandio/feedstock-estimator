import os
import urllib.parse
import requests
from dotenv import load_dotenv

import pandas as pd
import geopandas as gpd
import pyproj
from shapely.geometry import Polygon
from shapely.ops import transform

# External project imports
from backend import PrepGoldView  # noqa: F401  # Imported for the __main__ example

# --------------------------------------------------------------------------------------
#  Environment
# --------------------------------------------------------------------------------------

# Load environment variables from the .env file (needed for the Bing Maps API key)
load_dotenv()


# --------------------------------------------------------------------------------------
#  Core calculator
# --------------------------------------------------------------------------------------

class MunicipalityFeedstockCalculator:
    """Compute reachable feedstock *only* for arable land ('has' columns).

    All logic related to kTon or head-count columns has been removed so that
    ''calculate_feedstock_tonnage'' now focuses exclusively on hectare-based
    ("has") metrics.
    """

    def __init__(
        self,
        gdf: gpd.GeoDataFrame,
        longitude: float,
        latitude: float,
        distances: list[int] | None = None,
        times: list[int] | None = None,
        flag: str = "spain",
        bingkey: str | None = None,
    ) -> None:
        # Input data
        self.gdf = gdf
        self.longitude = longitude
        self.latitude = latitude

        # Isochrone parameters
        self.distances = distances or []
        self.times = times or []

        # Column selectors
        self.geography_col = "mun_name"
        self.has_cols = [col for col in gdf.columns if "Seminativi" in col]

        # Misc.
        self.bingkey = bingkey or os.getenv("BING_MAPS_API_KEY")
        self.flag = flag

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def calculate_feedstock_tonnage(self):  # keep original name for compatibility
        """Calculate reachable feedstock in hectares (``df_has``).

        Returns
        -------
        df_has : pandas.DataFrame
            Reachable feedstock by hectare ("has") for each isochrone.
        gdf_isochrones : geopandas.GeoDataFrame
            GeoDataFrame containing the generated isochrone geometries.
        """
        # Initialise the output frame using the has-columns as index
        df_has = pd.DataFrame(index=self.has_cols)

        # Generate isochrones (distance- and/or time-based)
        gdf_isochrones = self.calculate_isochrones()

        # Aggregate feedstock for each isochrone ring
        for isochrone in gdf_isochrones["isochrone"].unique():
            gdf_overlap = self._calculate_overlapping_area(isochrone, gdf_isochrones)
            gdf_overlap["overlap_area"] = gdf_overlap["overlap_area"].astype(float)
            gdf_reduced = self._calculate_area_scaling(gdf_overlap)

            # Accumulate scaled feedstock values
            df_has = self._sum_feedstock(df_has, gdf_reduced, self.has_cols, isochrone)

        return df_has, gdf_isochrones

    # ------------------------------------------------------------------
    #  Isochrone helpers
    # ------------------------------------------------------------------

    def calculate_isochrones(self):
        """Generate isochrones around the reference location."""
        gdf_iso = gpd.GeoDataFrame(columns=["isochrone", "geometry"], geometry="geometry")

        # Distance-based isochrones
        for km in self.distances:
            iso = self._calculate_bing_isochrone_distance_time(distances=km)
            gdf_iso = pd.concat(
                [
                    gdf_iso,
                    gpd.GeoDataFrame(
                        {"isochrone": [f"{int(km)} km"], "geometry": [iso]},
                        crs="epsg:4326",
                    ),
                ]
            )

        # Time-based isochrones
        for mins in self.times:
            iso = self._calculate_bing_isochrone_distance_time(times=mins)
            gdf_iso = pd.concat(
                [
                    gdf_iso,
                    gpd.GeoDataFrame(
                        {"isochrone": [f"{int(mins)} mins"], "geometry": [iso]},
                        crs="epsg:4326",
                    ),
                ]
            )

        return gdf_iso

    def _calculate_bing_isochrone_distance_time(
        self,
        distances: int | None = None,
        times: int | None = None,
        travel_mode: str = "truck",
        distance_unit: str = "km",
        time_unit: str = "minute",
    ) -> Polygon:
        """Call the Bing Maps Isochrone API and return the resulting polygon."""
        base_url = "https://dev.virtualearth.net"
        endpoint = "/REST/v1/Routes/Isochrones?"
        address = f"{self.latitude},{self.longitude}"

        params: dict[str, str | int] = {"waypoint": address, "travelMode": travel_mode}

        if distances is not None:
            params |= {
                "distanceUnit": distance_unit,
                "optimize": "distance",
                "maxDistance": distances,
            }
        elif times is not None:
            params |= {"timeUnit": time_unit, "optimize": "time", "maxTime": times}
        else:
            raise ValueError("Either 'distances' or 'times' must be provided.")

        url = f"{base_url}{endpoint}{urllib.parse.urlencode(params)}&key={self.bingkey}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        coords = (
            response.json()["resourceSets"][0]["resources"][0]["polygons"][0]["coordinates"][0]
        )
        polygon = Polygon(coords)

        # Flip coordinates (lat, lon ➜ lon, lat)
        return transform(lambda x, y: (y, x), polygon)

    # ------------------------------------------------------------------
    #  Spatial aggregation helpers
    # ------------------------------------------------------------------

    def _calculate_overlapping_area(
        self, isochrone, gdf_isochrones: gpd.GeoDataFrame, epsg: int = 3035
    ) -> gpd.GeoDataFrame:
        """Intersect municipalities with a given isochrone and measure overlap."""
        gdf_overlap = gpd.overlay(
            self.gdf[[self.geography_col, "geometry"]],
            gdf_isochrones.loc[gdf_isochrones["isochrone"] == isochrone],
            how="intersection",
        )
        gdf_overlap["overlap_area"] = gdf_overlap.to_crs(epsg=epsg).geometry.area
        return gdf_overlap

    def _calculate_area_scaling(self, gdf_overlap: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Scale municipality attributes by the proportion of area inside isochrone."""
        gdf_reduced = self.gdf.loc[
            self.gdf[self.geography_col].isin(gdf_overlap[self.geography_col].unique())
        ]
        gdf_reduced = gdf_reduced.merge(
            gdf_overlap[[self.geography_col, "overlap_area"]],
            on=self.geography_col,
            how="left",
        )
        gdf_reduced["area_scaling"] = gdf_reduced["overlap_area"] / gdf_reduced["area"]
        return gdf_reduced

    def _sum_feedstock(
        self,
        df: pd.DataFrame,
        gdf_reduced: gpd.GeoDataFrame,
        cols: list[str],
        isochrone: str,
    ) -> pd.DataFrame:
        """Helper to aggregate and accumulate scaled feedstock columns."""
        return df.merge(
            pd.DataFrame(
                gdf_reduced[cols].multiply(gdf_reduced["area_scaling"], axis=0).sum(axis=0),
                columns=[isochrone],
            ),
            left_index=True,
            right_index=True,
        )


# --------------------------------------------------------------------------------------
#  Quick-start example (for local testing)
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Note: this block is only for manual testing and demonstration purposes.
    a = PrepGoldView(flag="italy")
    gdf_v2 = a.merged_df

    # Ensure CRS is set correctly
    gdf = gdf_v2.set_crs(pyproj.CRS.from_epsg(4326), allow_override=True)

    # Instantiate calculator (example coordinates: Milan, IT)
    calculator = MunicipalityFeedstockCalculator(
        gdf,
        longitude=9.1824,
        latitude=45.4685,
        distances=[50],
        times=[],
        flag="italy",
    )

    df_has, gdf_isochrones = calculator.calculate_feedstock_tonnage()

    print("Reachable feedstock (has):\n", df_has)
    print("\nGenerated isochrones:\n", gdf_isochrones)
