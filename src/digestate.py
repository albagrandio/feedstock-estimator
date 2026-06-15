import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely import wkb
import requests, urllib
from shapely.wkt import loads as wkt_loads
import json, numpy as np, os
from shapely.geometry.polygon import Polygon
from shapely.ops import transform
from dotenv import load_dotenv
from src.constants import SHAPEFILE_SPAIN, SIGPAC
from src.backend import PrepDigestateView
import pyproj
import polars as pl

load_dotenv()
# read dataset from file


def calculate_absorption_lazy(lazy_df, mapping_table):
    # Define column names
    col_vul_intersection_flag = "restricted_zone_flag"
    col_parc_product_id = "par_produc"
    col_irrigation_coefficient = "irrigation_coefficient"
    col_slope = "average_slope"
    col_dosis_max_n = "Dosis Maxima N"

    # Define mapping table column names
    map_col_codigo = "Product_id"
    map_col_dosis_regadio = "Irrigated"
    map_col_dosis_secano = "Dry"
    map_col_suelo_vulnerable = "Vulnerable"
    map_col_pendiente_mayor = "Slope Theshold"

    lazy_df = lazy_df.with_columns(pl.col("restricted_zone_flag").cast(pl.Int32))  # Cast to numeric type
    # Perform join to bring mapping values into LazyFrame
    joined_df = lazy_df.join(mapping_table, left_on=col_parc_product_id, right_on=map_col_codigo, how="left")

    # Apply dose calculation logic directly in Polars expressions
    result_df = joined_df.with_columns(
        # Logic for calculating the maximum nitrogen absorption 100 due to assumed scaling factor of 10 in dataset
        pl.when((pl.col(col_slope) > 100).or_(pl.col(col_parc_product_id) == 0))
        .then(0)  # Slope threshold check
        .otherwise(
            # Logic when slope <= 80
            pl.when(pl.col(col_irrigation_coefficient) == 1)
            .then(
                # Minimum of Irrigated and Vulnerable if restricted_flag == 1
                pl.when(pl.col(col_vul_intersection_flag) == 1)
                .then(
                    pl.min_horizontal(
                        [
                            pl.col(map_col_dosis_regadio),
                            pl.col(map_col_suelo_vulnerable),
                        ]
                    )
                )
                .otherwise(pl.col(map_col_dosis_regadio))
            )
            .otherwise(
                # For Dry: Minimum of Dry and Vulnerable if restricted_flag == 1
                pl.when(pl.col(col_vul_intersection_flag) == 1)
                .then(pl.min_horizontal([pl.col(map_col_dosis_secano), pl.col(map_col_suelo_vulnerable)]))
                .otherwise(pl.col(map_col_dosis_secano))
            )
        )
        .alias(col_dosis_max_n)  # Assign to the desired column name
    )

    return result_df


class IsochroneCalculator:
    """
    A class to calculate incremental isochrones and their associated areas.

    Attributes:
        longitude (float): The center longitude for isochrone calculation.
        latitude (float): The center latitude for isochrone calculation.
        gdf (GeoDataFrame): Original data GeoDataFrame.
        geography_col (str): Column name for geography identifiers.
    """

    def __init__(self, longitude, latitude, gdf, geography_col):
        """
        Initialize the IsochroneCalculator with the required data and parameters.

        Args:
            longitude (float): The center longitude.
            latitude (float): The center latitude.
            gdf (GeoDataFrame): The GeoDataFrame containing original data.
            geography_col (str): The column name for geography identifiers.
        """
        self.longitude = longitude
        self.latitude = latitude
        self.gdf = gdf
        self.geography_col = geography_col
        self.bingkey = os.getenv("BING_KEY")

    def calculate_incremental_isochrones(
        self,
        start_distance: int = 5,
        increment: int = 5,
        threshold_N=1000,
        isochrone_col: str = "isochrone",
        geometry_col: str = "geometry",
    ):
        """
        Calculate isochrones incrementally until a threshold area or nitrogen level is reached.

        Args:
            start_distance (int): Starting isochrone distance in km.
            increment (int): Distance increment for each step in km.
            threshold_N (float, optional): Minimum nitrogen threshold to be covered.

        Returns:
            tuple: A GeoDataFrame with isochrones and a GeoDataFrame with the reduced data.
        """
        gdf_iso = gpd.GeoDataFrame(columns=[isochrone_col, geometry_col], geometry="geometry", crs="epsg:4326")
        current_distance = start_distance
        total_covered_area = 0
        total_covered_N = 0

        while threshold_N is None or total_covered_N < threshold_N:
            # Calculate the isochrone
            iso = self._calculate_bing_isochrone(current_distance)

            # Create a GeoDataFrame for this isochrone
            gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
            gdf_iso_temp[isochrone_col] = f"{current_distance} km"

            # Add to the main GeoDataFrame
            gdf_iso = pd.concat([gdf_iso, gdf_iso_temp])

            # Process overlaps and calculate areas
            gdf_reduced, total_covered_area, total_covered_N = self._process_overlaps(gdf_iso_temp)

            print(f"Isochrone {current_distance} km covers {total_covered_area:.2f} hectares")
            print(f"Isochrone {current_distance} km covers {total_covered_N:.2f} N")

            if total_covered_N >= threshold_N:
                print(f"Threshold of {threshold_N} N reached")
                break

            # Increment the distance for the next iteration
            current_distance += increment

            if current_distance > 39:
                return None, None

        return gdf_iso, gdf_reduced

    def _calculate_bing_isochrone(
        self,
        distances=None,
        times=None,
        travel_mode: str = "truck",
        distance_unit: str = "km",
        time_unit: str = "minute",
    ):
        BASE = "https://dev.virtualearth.net"
        GEOCODE_PATH = "/REST/v1/Routes/Isochrones?"
        address = f"{self.latitude},{self.longitude}"
        params = {
            "waypoint": address,
            "travelMode": travel_mode,
        }

        if distances:
            params["distanceUnit"] = distance_unit
            params["optimize"] = "distance"
            params["maxDistance"] = distances
        elif times:
            params["timeUnit"] = time_unit
            params["optimize"] = "time"
            params["maxTime"] = times

        url = f"{BASE}{GEOCODE_PATH}{urllib.parse.urlencode(params)}&key={self.bingkey}"
        response = requests.get(url)
        result = response.json()

        if response.status_code != 200:
            raise requests.HTTPError("Unsuccessful Request", response)

        result_coordinates = result["resourceSets"][0]["resources"][0]["polygons"][0]["coordinates"][0]
        result_polygons = Polygon(result_coordinates)
        result_polygons = transform(lambda x, y: (y, x), result_polygons)  # flip latitutde and longitude
        return result_polygons

    def _process_overlaps(self, gdf_iso_temp):
        """
        Process overlaps between isochrones and original data to calculate areas.

        Args:
            gdf_iso_temp (GeoDataFrame): Temporary GeoDataFrame for the current isochrone.

        Returns:
            tuple: Updated GeoDataFrame, total covered area, and total covered nitrogen level.
        """
        # Calculate overlap and area scaling
        gdf_overlap = gpd.overlay(self.gdf[[self.geography_col, "geometry"]], gdf_iso_temp, how="intersection")
        gdf_overlap["overlap_area"] = gdf_overlap.to_crs(epsg=3035).geometry.area

        gdf_reduced = self.gdf.loc[self.gdf[self.geography_col].isin(gdf_overlap[self.geography_col].unique())]
        gdf_reduced = pd.merge(
            gdf_reduced,
            gdf_overlap[[self.geography_col, "overlap_area"]],
            on=self.geography_col,
            how="left",
        )

        gdf_reduced["area_scaling"] = gdf_reduced["overlap_area"] / gdf_reduced["surface_area"]
        gdf_reduced["surface_area"] = gdf_reduced["surface_area"] / 10000
        gdf_reduced["final_surface"] = gdf_reduced["surface_area"] * gdf_reduced["area_scaling"]

        # Calculate total nitrogen levels
        gdf_reduced["total_N"] = gdf_reduced["final_surface"] * gdf_reduced["Dosis Maxima N"]

        # Calculate total covered area and nitrogen
        total_covered_area = gdf_reduced["final_surface"].sum()
        total_covered_N = gdf_reduced["total_N"].sum()

        return gdf_reduced, total_covered_area, total_covered_N
