import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import Polygon

# from src.constants import (
#    crops,
#    TONNAGECOWSLURRY,
#    TONNAGECOWMANURE,
#    SHEEPGOATMANURE,
# )
from src.backend import PrepGoldView
from src.schemas.italy import feedstock_dict
import os
from dotenv import load_dotenv
from shapely.ops import transform
import numpy as np
import urllib.parse
from shapely.wkt import loads as wkt_loads
from src.utils import load_constants
import pyproj


# Load environment variables from the .env file
load_dotenv()


class MunicipalityFeedstockCalculator:
    def __init__(self, gdf, longitude, latitude, distances=None, times=None, flag: str = "spain"):
        self.gdf = gdf
        self.longitude = longitude
        self.latitude = latitude
        self.distances = distances
        self.times = times
        self.geography_col = "mun_name"
        self.kTon_cols = [col for col in gdf.columns if "(ktn)" in col]
        self.heads_cols = [col for col in gdf.columns if "(no. heads)" in col]
        self.bingkey = os.getenv("BING_KEY")
        self.flag = flag

    def calculate_feedstock_tonnage(self):
        """Calculate the reachable feedstock from a specified location in the prescribed distances and/or times.

        Returns:
        - df_heads: DataFrame detailing the reachable feedstock by headcount.
        - df_tonnage: DataFrame detailing the reachable feedstock by tonnage.
        - gdf_isochrones: GeoDataFrame of the generated isochrones."""
        df_tonnage = pd.DataFrame(index=self.kTon_cols)
        df_heads = pd.DataFrame(index=self.heads_cols)

        gdf_isochrones = self.calculate_isochrones()

        for isochrone in gdf_isochrones["isochrone"].unique():
            gdf_overlap = self._calculate_overlapping_area(isochrone, gdf_isochrones)
            gdf_overlap["overlap_area"] = gdf_overlap["overlap_area"].astype("float")
            gdf_reduced = self._calculate_area_scaling(gdf_overlap)

            # Sum feedstock and scale it based on area scaling
            df_tonnage = self._sum_feedstock(df_tonnage, gdf_reduced, self.kTon_cols, isochrone)
            print(df_tonnage.head())
            df_heads = self._sum_feedstock(df_heads, gdf_reduced, self.heads_cols, isochrone)
            print(df_heads.head())

        # TODO remove once yaml file is completed
        # if self.flag == "italy":
        # return df_tonnage, df_heads, gdf_isochrones

        df_tonnage, df_heads = self._add_totals(df_tonnage, df_heads, self.flag)

        return df_tonnage, df_heads, gdf_isochrones

    def calculate_isochrones(self):
        """Wrapper to calculate isochrones using Bing or Mapbox APIs."""
        gdf_iso = gpd.GeoDataFrame(columns=["isochrone", "geometry"], geometry="geometry")

        for km in self.distances:
            iso = self._calculate_bing_isochrone_distance_time(distances=km)
            gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
            gdf_iso_temp["isochrone"] = f"{int(km)} km"
            gdf_iso = pd.concat([gdf_iso, gdf_iso_temp])

        for mins in self.times:
            iso = self._calculate_bing_isochrone_distance_time(times=mins)
            gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
            gdf_iso_temp["isochrone"] = f"{int(mins)} mins"
            gdf_iso = pd.concat([gdf_iso, gdf_iso_temp])

        return gdf_iso

    def _calculate_bing_isochrone_distance_time(
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

    def _calculate_overlapping_area(self, isochrone, gdf_isochrones, epsg: int = 3035) -> gpd.GeoDataFrame:

        gdf_overlap = gpd.overlay(
            self.gdf[[self.geography_col, "geometry"]],
            gdf_isochrones.loc[gdf_isochrones["isochrone"] == isochrone],
            how="intersection",
        )
        gdf_overlap["overlap_area"] = gdf_overlap.to_crs(epsg=epsg).geometry.area
        return gdf_overlap

    def _calculate_area_scaling(self, gdf_overlap):
        gdf_reduced = self.gdf.loc[self.gdf[self.geography_col].isin(gdf_overlap[self.geography_col].unique())]
        gdf_reduced = pd.merge(
            gdf_reduced,
            gdf_overlap[[self.geography_col, "overlap_area"]],
            on=self.geography_col,
            how="left",
        )
        gdf_reduced["area_scaling"] = gdf_reduced["overlap_area"] / gdf_reduced["area"]
        return gdf_reduced

    def _sum_feedstock(self, df: pd.DataFrame, gdf_reduced, cols, isochrone):
        df = df.merge(
            pd.DataFrame(
                gdf_reduced[cols].multiply(gdf_reduced["area_scaling"], axis=0).sum(axis=0),
                columns=[isochrone],
            ),
            left_index=True,
            right_index=True,
        )
        return df

    def _add_totals(self, df_tonnage, df_heads, country: str = "spain"):

        config = load_constants(country)
        TONNAGECOWSLURRY = config.get("dataset_columns", {}).get("TONNAGECOWSLURRY")
        TONNAGECOWMANURE = config.get("dataset_columns", {}).get("TONNAGECOWMANURE")
        SHEEPGOATMANURE = config.get("dataset_columns", {}).get("SHEEPGOATMANURE")
        CROPS = config.get("dataset_columns", {}).get("crops")
        # calculate the total cow slurry feedstock
        tonnageCowSlurry = [col for col in self.kTon_cols if any(sub in col for sub in TONNAGECOWSLURRY)]
        headsCowSlurry = [col for col in self.heads_cols if any(sub in col for sub in TONNAGECOWSLURRY)]
        totalCowSlurryTonnage = pd.DataFrame(df_tonnage.loc[tonnageCowSlurry].sum()).T
        totalCowSlurryTonnage.index = ["Total Cow Slurry (kTon)"]
        totalCowSlurryHeads = pd.DataFrame(df_heads.loc[headsCowSlurry].sum()).T
        totalCowSlurryHeads.index = ["Total Cow Slurry (no. heads)"]

        # calculate the total cow manure feedstock
        cowManureTonnage = [col for col in self.kTon_cols if any(sub in col for sub in TONNAGECOWMANURE)]
        cowManureHeads = [col for col in self.heads_cols if any(sub in col for sub in TONNAGECOWMANURE)]
        totalCowManureTonnage = pd.DataFrame(df_tonnage.loc[cowManureTonnage].sum()).T
        totalCowManureTonnage.index = ["Total Cow Manure (kTon)"]
        totalCowManureHeads = pd.DataFrame(df_heads.loc[cowManureHeads].sum()).T
        totalCowManureHeads.index = ["Total Cow Manure (no. heads)"]

        # calculate the total Sheep and Goats feedstock
        sheepGoatsTonnage = [col for col in self.kTon_cols if any(sub in col for sub in SHEEPGOATMANURE)]
        sheepGoatsHeads = [col for col in self.heads_cols if any(sub in col for sub in SHEEPGOATMANURE)]
        totalSheepGoatsTonnage = pd.DataFrame(df_tonnage.loc[sheepGoatsTonnage].sum()).T
        totalSheepGoatsTonnage.index = ["Total Sheep & Goats Manure (kTon)"]
        totalSheepGoatsHeads = pd.DataFrame(df_heads.loc[sheepGoatsHeads].sum()).T
        totalSheepGoatsHeads.index = ["Total Sheep & Goats (no. heads)"]

        cropTonnage = CROPS
        totalCropsTonnage = pd.DataFrame(df_tonnage.loc[cropTonnage].sum()).T
        totalCropsTonnage.index = ["Total Crops (ktn)"]

        df_tonnage = pd.concat(
            [
                df_tonnage,
                totalCowSlurryTonnage,
                totalCowManureTonnage,
                totalSheepGoatsTonnage,
                totalCropsTonnage,
            ]
        )
        df_heads = pd.concat([df_heads, totalCowSlurryHeads, totalCowManureHeads, totalSheepGoatsHeads])

        FINALTONNAGECOLS = config.get("dataset_columns", {}).get("FINALTONNAGECOLS").keys()
        FINALHEADSCOLS = config.get("dataset_columns", {}).get("FINALHEADSCOLS")

        df_tonnage = df_tonnage.loc[FINALTONNAGECOLS]

        df_tonnage = np.round(df_tonnage, 1)
        print(df_tonnage)
        print(df_tonnage.columns)

        df_heads = df_heads.loc[FINALHEADSCOLS]
        df_heads = np.round(df_heads, 0)
        return df_tonnage, df_heads


if __name__ == "__main__":
    a = PrepGoldView(flag="italy")
    gdf_v2 = a.merged_df
    print(gdf_v2.head())
    crs = pyproj.CRS.from_epsg(4326)
    gdf = gdf_v2.set_crs(crs, allow_override=True)
    # df_v2 = gdf_v2.set_crs("EPSG:4326")
    print(type(gdf_v2))

    # logging.getLogger().setLevel(logging.INFO)
    # gdf_v2 = pd.read_csv(
    #    "/Users/aditi.chetty/Documents/Repos/Verdalia/notebooks/italy_feedstock.csv",
    #    dtype=feedstock_dict,
    # )
    ##gdf_v2["geometry"] = gdf_v2["geometry"].apply(wkt_loads)
    # gdf = gpd.GeoDataFrame(gdf_v2, geometry="geometry")
    # gdf_v2 = gdf.set_crs("EPSG:4326")
    # crs = pyproj.CRS.from_epsg(4326)
    # gdf = gdf.set_crs(crs, allow_override=True)
    # gdf_v2 = gdf.to_crs(epsg=4326)

    calculator = MunicipalityFeedstockCalculator(
        gdf_v2,
        longitude=9.1824,  # -2.1654161173867994,
        latitude=45.4685,  # 39.21477034472512,
        distances=[50],
        times=[],
        flag="italy",
    )
    df_tonnage, df_heads, gdf_isochrones = calculator.calculate_feedstock_tonnage()
    print(df_heads)
    print(df_tonnage)
    # df_tonnage.to_csv("italy_feedstock_tonnage.csv")

#
