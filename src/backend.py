import urllib.parse
import os
from dotenv import load_dotenv
import requests
from sqlalchemy import create_engine
import pandas as pd
import geopandas as gpd
from shapely import wkb
from shapely.geometry.polygon import Polygon
from shapely.ops import transform
import numpy as np
from sqlalchemy import text
from shapely import wkb
import polars as pl
import pyproj
from shapely.wkt import loads as wkt_loads
import connectorx as cx
from src.schemas.italy import column_mapping
from dotenv import load_dotenv
import streamlit as st

load_dotenv()


class BaseDatasetPreparer:
    """Base class for dataset preparation tasks, including database connection and shared utilities."""

    def __init__(self):
        """
        Initialize the BaseDatasetPreparer with a database configuration.
        """
        self.DATABASE_TYPE = os.getenv("DATABASE_TYPE")
        self.DBAPI = os.getenv("DBAPI")
        self.USER = os.getenv("USER")
        self.PASSWORD = os.getenv("PASSWORD")
        self.HOST = os.getenv("HOST")
        self.PORT = "5432"
        self.DATABASE = "postgres"

        # Create connection string and engine
        self.connection_string = (
            f"{self.DATABASE_TYPE}+{self.DBAPI}://{self.USER}:{self.PASSWORD}@" f"{self.HOST}:{self.PORT}/{self.DATABASE}"
        )
        self.engine = self._create_engine()
        self.uri = f"postgresql://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DATABASE}"

    def _create_engine(self):
        """Create and return a SQLAlchemy engine."""
        return create_engine(self.connection_string)

    def _run_query(self, query: str) -> pd.DataFrame:
        """
        Execute a SQL query and return the result as a pandas DataFrame.

        Args:
            query (str): The SQL query to execute.

        Returns:
            pd.DataFrame: Query result.
        """
        return pd.read_sql(query, self.engine)

    def _convert_wkb(self, df: pd.DataFrame, geo_col: str = "geometry") -> pd.DataFrame:
        """
        Convert WKB hex strings to geometry objects

         Args:
             query (str): The SQL query to execute.

         Returns:
             pd.DataFrame: Query result.
        """
        # Function to safely parse WKB

        df[geo_col] = df[geo_col].apply(lambda x: wkb.loads(x, hex=True))
        return df

    def _prepare_geo_data(self, shapefile: gpd.GeoDataFrame, geometry: str = "geometry") -> gpd.GeoDataFrame:
        """_query data from postgreSQL database convert wkb strings to geometry and return geopandas dataframe_

        Returns:
            gpd.GeoDataFrame
        """
        query: str = f"SELECT * FROM {shapefile}"  # TODO add assert to make sure its not Nan and add logging to write
        geo_df: gpd.GeoDataFrame = self._run_query(query)
        # Convert WKB hex strings to geometry objects
        try:
            geo_df: gpd.GeoDataFrame = self._convert_wkb(geo_df, geometry)
        except Exception as e:  # TODO add what exception to catch
            # create a new geometry column from geometry wkt
            geo_df["geometry"] = geo_df[geometry].apply(wkt_loads)

        gdf = gpd.GeoDataFrame(geo_df, geometry=geo_df["geometry"], crs="EPSG:4326")

        return gdf

    def _prepare_geo_data_polars(self, shapefile: str, geometry: str = "geometry", crs_flag: str = False) -> gpd.GeoDataFrame:
        """_query data as polars from postgreSQL database convert wkb strings to geometry

        Returns:
            gpd.GeoDataFrame
        """
        query = f"SELECT * FROM {shapefile}"

        geo_df = pl.read_database_uri(query, self.uri, engine="connectorx").lazy()
        geo_df_final = (
            geo_df.collect().to_pandas()
        )  # TODO add assert to make sure its not Nan and add logging to write and add unit

        geo_df_final["geometry"] = geo_df_final[geometry].apply(wkt_loads)

        if crs_flag:  # this allows us to change the geo depending on the dataframe read from postgres
            geo_df_final = gpd.GeoDataFrame(geo_df_final, geometry=geo_df_final["geometry"], crs="EPSG:32633")
            geo_df_final = geo_df_final.to_crs("EPSG:4326")
        else:
            geo_df_final = gpd.GeoDataFrame(geo_df_final, geometry=geo_df_final["geometry"], crs="EPSG:4326")
        return geo_df_final


class PrepGoldView(BaseDatasetPreparer):
    """_summary_"""

    SHAPE_SPAIN: str = "georef_spain_municipio"
    DF_HEADS: str = "view_df_heads"
    DF_TONNAGE: str = "df_tonnage"

    def __init__(self, flag: str = "spain"):
        """The pipeline for retrieving the gold view from postgres and processing slightly so its ready for the app
        Args:

        """
        # Initialize the base class
        super().__init__()

        # Create connection string
        # Create engine
        self.connection_string = (
            f"{self.DATABASE_TYPE}+{self.DBAPI}://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DATABASE}"
        )
        self.engine = self._create_engine()
        if flag == "italy":  # TODO think about whether a dictionary might work as more countries are added
            self.merged_df = self._prepare_geo_data_polars("it_consistency_of_farms")
            self.merged_df = self.merged_df.rename(columns=column_mapping)
            self.biovic = self._prepare_geo_data_polars(
                "plant_location_info_manual_2025", geometry="geometry_wkt", crs_flag=True
            )
        else:
            self.geo_dataset = self._prepare_geo_data(shapefile=self.SHAPE_SPAIN)
            self.merged_df = self._mergefeedstock_datasets()
            self.biovic = self._prepare_geo_data_polars("sp_agriculture_biovic_facilities_geojson", geometry="geometry_wkt")

    def _mergefeedstock_datasets(
        self,
        PROV: str = "PROV",
        MUNI: str = "MUNI",
        CCAA: str = "CCAA",
    ) -> pd.DataFrame:
        """_summary_

        Args:

        Returns:
            pd.DataFrame: _description_
        """
        with self.engine.connect() as connection:
            df_heads = pd.read_sql(text(f"SELECT * FROM {self.DF_HEADS}"), connection)
            df_tonnage = pd.read_sql(text(f"SELECT * FROM {self.DF_TONNAGE}"), connection)
        df_tonnage[MUNI] = df_tonnage[MUNI].astype(int).astype(str)
        df_tonnage[PROV] = df_tonnage[PROV].astype(int).astype(str)
        df_tonnage[CCAA] = df_tonnage[CCAA].astype(int).astype(str)
        df_heads[MUNI] = df_heads[MUNI].astype(int).astype(str)
        df_heads[PROV] = df_heads[PROV].astype(int).astype(str)
        df_heads[CCAA] = df_heads[CCAA].astype(int).astype(str)

        dfMuni = df_tonnage.merge(df_heads, on=[CCAA, PROV, MUNI])

        for index, row in dfMuni.iterrows():
            if len(row[MUNI]) < 5:
                dfMuni.loc[index, MUNI] = "0" + dfMuni.loc[index, MUNI]
            if len(row[PROV]) < 2:
                dfMuni.loc[index, PROV] = "0" + dfMuni.loc[index, PROV]
            if len(row[CCAA]) < 2:
                dfMuni.loc[index, CCAA] = "0" + dfMuni.loc[index, CCAA]

        gdfMuniTonnage = self.geo_dataset[
            [
                "acom_code",
                "acom_name",
                "prov_code",
                "prov_name",
                "mun_code",
                "mun_name",
                "geometry",
            ]
        ].merge(dfMuni, left_on="mun_code", right_on=MUNI, how="right")

        gdfMuniTonnage["area"] = gdfMuniTonnage.to_crs(epsg=3035).geometry.area

        # logging.info("Successfully prepared Postcode Sector DataFrame")
        return gdfMuniTonnage


class PrepDigestateView(BaseDatasetPreparer):
    def __init__(
        self,
        lat: float = None,
        lon: float = None,
        shapefile: str = None,
        sigpac: str = None,
        mun_code: str = None,
        prov_code: str = "prov_code",
        geometry_col: str = "geometry",
    ):
        """
        The pipeline for retrieving the gold view from PostgreSQL and processing slightly so it's ready for the app.
        Args:
            lat (float, optional): Latitude value for the starting point. Defaults to session state latitude.
            lon (float, optional): Longitude value for the starting point. Defaults to session state longitude.
            shapefile (str, optional): Name of the shapefile. Defaults to None.
            sigpac (str, optional): Name of the SIGPAC table. Defaults to None.
        """
        super().__init__()

        # Set up dynamic and static properties
        self.bing_maps_key = os.getenv("BING_KEY")
        self.lat = lat if lat is not None else st.session_state.latitude
        self.lon = lon if lon is not None else st.session_state.longitude
        self.distance_km = 40
        self.geography_col = "geography_level_4_id"
        self.shapefile = self._prepare_geo_data(shapefile, geometry_col)
        self.SIGPAC = sigpac
        self.mun_code = mun_code  # this the defulat for spain
        self.prov_code = prov_code  # this the defulat for spain

    def process_sigpac_data(self):
        """
        Main pipeline to find municipalities within the isochrone, filter crop data, and return the result.

        Args:
            spain_gdf (GeoDataFrame): GeoDataFrame containing Spanish geographic data.

        Returns:
            GeoDataFrame: Filtered SIGPAC data.
        """

        # Step 1: Find municipalities within the isochrone
        eligible_mun_list, prov_list = self.find_municipalities_within_isochrone()
        eligible_mun_list = eligible_mun_list.tolist() if isinstance(eligible_mun_list, np.ndarray) else eligible_mun_list
        prov_list = prov_list.tolist() if isinstance(prov_list, np.ndarray) else prov_list

        ids_array = ",".join(map(str, eligible_mun_list))
        flag = st.session_state.flag
        geography_prov_col: str = "geography_level_3_id" if flag == "italy" else "geography_level_2_id"

        query_italy = f"""
            SELECT object_id,
                   par_produc,
                   product_name,
                   country_id,
                   geography_level_1_id,
                   geography_level_2_id,
                   geography_level_3_id,
                   geography_level_4_id,
                   surface_area,
                   average_slope,
                   irrigation_coefficient,
                   restricted_zone_flag,
                   geometry_wkt
            FROM {self.SIGPAC}
            WHERE {geography_prov_col} = ANY(ARRAY[{','.join(map(str, prov_list))}]::INTEGER[])
            AND  {self.geography_col} = ANY(ARRAY[{ids_array}]::INTEGER[])
            """

        query = f"""
            SELECT object_id,
                   CAST(par_produc AS FLOAT) AS par_produc,
                   country_id,
                   geography_level_1_id,
                   geography_level_2_id,
                   geography_level_4_id,
                   surface_area,
                   average_slope,
                   irrigation_coefficient,
                   restricted_zone_flag,
                   geometry_wkt
            FROM {self.SIGPAC}
            WHERE {geography_prov_col} = ANY(ARRAY[{','.join(map(str, prov_list))}]::INTEGER[])
            AND  {self.geography_col} = ANY(ARRAY[{ids_array}]::INTEGER[])


            """

        filtered_sigpac_data: pl.LazyFrame = pl.read_database_uri(
            query_italy if flag == "italy" else query,
            self.uri,
            partition_on=geography_prov_col,
            partition_num=20,
            engine="connectorx",
        ).lazy()

        return filtered_sigpac_data

    def find_municipalities_within_isochrone(
        self,
        geometry_col: str = "geometry",
        isochrone_col: str = "isochrone",
    ) -> tuple[list, list]:

        # prepare shapefile by selecting the right
        geo_df = gpd.GeoDataFrame(self.shapefile, geometry=geometry_col, crs="epsg:4326")

        gdf_iso_filter = gpd.GeoDataFrame(
            columns=[isochrone_col, geometry_col],
            geometry=geometry_col,
            crs="epsg:4326",
        )

        iso = self._calculate_bing_isochrone_distance_time(distances=self.distance_km)

        # Create a GeoDataFrame for this isochrone
        gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
        gdf_iso_temp[isochrone_col] = f"{self.distance_km} km"

        # Add to the main GeoDataFrame
        gdf_iso_filter = pd.concat([gdf_iso_filter, gdf_iso_temp])

        gdf_overlap = gpd.overlay(
            geo_df[[self.mun_code, self.prov_code, geometry_col]],
            gdf_iso_filter,
            how="intersection",
        )
        mun_list: list = gdf_overlap[self.mun_code].unique()
        prov_list: list = gdf_overlap[self.prov_code].unique()

        return mun_list, prov_list

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
        address = f"{self.lat},{self.lon}"
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

        url = f"{BASE}{GEOCODE_PATH}{urllib.parse.urlencode(params)}&key={self.bing_maps_key}"
        response = requests.get(url)
        result = response.json()

        if response.status_code != 200:
            raise requests.HTTPError("Unsuccessful Request", response)

        result_coordinates = result["resourceSets"][0]["resources"][0]["polygons"][0]["coordinates"][0]
        result_polygons = Polygon(result_coordinates)
        result_polygons = transform(lambda x, y: (y, x), result_polygons)  # flip latitutde and longitude
        return result_polygons


if __name__ == "__main__":

    shapefile_italy = "geofiles_italy_shape"
    mun_code = "mun_code"
    digestate_view = PrepDigestateView(
        lat=45.5416, lon=10.2118, shapefile=shapefile_italy, mun_code="mun_code", prov_code="prov_code"
    )

    dig = PrepDigestateView()
    # test if this works with just shapefile data
    test = dig.find_municipalities_within_isochrone()
    # then filter using resulting list to see if it works
