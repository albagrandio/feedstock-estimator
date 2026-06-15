from shapely.geometry import Point, Polygon
import pandas as pd
import geopandas as gpd
from backend import PrepGoldView
from schemas.italy import feedstock_dict
import os
from dotenv import load_dotenv
from shapely.ops import transform
import numpy as np
import urllib.parse
from shapely.wkt import loads as wkt_loads
from utils import load_constants
import pyproj
from Verdalia_feedstock_class import MunicipalityFeedstockCalculator

# Load environment variables from the .env file
load_dotenv()

class MunicipalityFeedstockBufferCalculator(MunicipalityFeedstockCalculator):
    """
    Igual que MunicipalityFeedstockCalculator, pero las 'isochrones'
    son buffers GEODÉSICOS (sobre WGS84) con radios en km.
    """

    def _geodesic_buffer(self, lat, lon, radius_km, n_points=360):
        geod = pyproj.Geod(ellps="WGS84")
        az = np.linspace(0, 360, num=n_points, endpoint=False)
        lats, lons = [], []
        for a in az:
            lon2, lat2, _ = geod.fwd(lon, lat, a, radius_km * 1000.0)
            lats.append(lat2); lons.append(lon2)
        lats.append(lats[0]); lons.append(lons[0])  # cerrar
        return Polygon(zip(lons, lats))

    def calculate_isochrones(self):
        self.distances = list(self.distances or [])
        self.times = list(self.times or [])
        if not self.distances and not self.times:
            raise ValueError("Debes proporcionar 'distances' (en km) o 'times'.")

        buffer_distances = list(self.distances)
        gdf_iso = gpd.GeoDataFrame(columns=["isochrone", "geometry"], geometry="geometry", crs="EPSG:4326")
        for km in buffer_distances:
            poly = self._geodesic_buffer(self.latitude, self.longitude, float(km), n_points=360)
            gdf_iso = pd.concat(
                [gdf_iso, gpd.GeoDataFrame({"isochrone": [f"{int(km)} km (buffer)"], "geometry": [poly]}, crs="EPSG:4326")],
                ignore_index=True
            )
        return gdf_iso

    def calculate_feedstock_tonnage(self):
        """Calculate the reachable feedstock from a specified location in the prescribed distances and/or times.

        Returns:
        - df_heads: DataFrame detailing the reachable feedstock by headcount.
        - df_tonnage: DataFrame detailing the reachable feedstock by tonnage.
        - gdf_isochrones: GeoDataFrame of the generated isochrones.
        """
        # Asegura CRS y área de referencia (3035) para escalado por intersección
        if self.gdf.crs is None:
            self.gdf = self.gdf.set_crs("EPSG:4326", allow_override=True)
        elif self.gdf.crs.to_string().lower() != "epsg:4326":
            self.gdf = self.gdf.to_crs(epsg=4326)

        if "area_m2_3035" not in self.gdf.columns:
            _gdf_3035 = self.gdf.to_crs(epsg=3035)
            self.gdf["area_m2_3035"] = _gdf_3035.geometry.area.values

        df_tonnage = pd.DataFrame(index=self.kTon_cols)
        df_heads = pd.DataFrame(index=self.heads_cols)

        gdf_isochrones = self.calculate_isochrones()

        for isochrone in gdf_isochrones["isochrone"].unique():
            # Intersección entre municipios y buffer geodésico
            gdf_overlap = gpd.overlay(
                self.gdf[[self.geography_col, "geometry"]],
                gdf_isochrones.loc[gdf_isochrones["isochrone"] == isochrone, ["geometry"]],
                how="intersection",
            )

            if gdf_overlap.empty:
                df_tonnage[isochrone] = 0.0
                df_heads[isochrone] = 0.0
                continue

            # Calcula área de solape en 3035 (m^2)
            gdf_overlap = gdf_overlap.to_crs(epsg=3035)
            gdf_overlap["overlap_area"] = gdf_overlap.geometry.area.astype("float")
            gdf_overlap = gdf_overlap.to_crs(epsg=4326)

            # Reduce a los municipios afectados y une el área de solape
            gdf_reduced = self.gdf.loc[
                self.gdf[self.geography_col].isin(gdf_overlap[self.geography_col].unique())
            ].copy()

            gdf_reduced = pd.merge(
                gdf_reduced,
                gdf_overlap[[self.geography_col, "overlap_area"]],
                on=self.geography_col,
                how="left",
            )

            # Escalado por área (cap [0,1])
            gdf_reduced["overlap_area"] = gdf_reduced["overlap_area"].fillna(0.0)
            denom = gdf_reduced["area_m2_3035"].replace({0: np.nan})
            gdf_reduced["area_scaling"] = (gdf_reduced["overlap_area"] / denom).clip(lower=0, upper=1).fillna(0)

            # Asegura tipos numéricos y columnas presentes
            cols_ton = [c for c in self.kTon_cols if c in gdf_reduced.columns]
            cols_head = [c for c in self.heads_cols if c in gdf_reduced.columns]
            gdf_reduced[cols_ton] = gdf_reduced[cols_ton].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            gdf_reduced[cols_head] = gdf_reduced[cols_head].apply(pd.to_numeric, errors="coerce").fillna(0.0)

            # Suma ponderada por área
            ton_series = gdf_reduced[cols_ton].multiply(gdf_reduced["area_scaling"], axis=0).sum(axis=0)
            head_series = gdf_reduced[cols_head].multiply(gdf_reduced["area_scaling"], axis=0).sum(axis=0)

            # Coloca en el DataFrame final, respetando el orden de índices objetivo
            df_tonnage[isochrone] = ton_series.reindex(self.kTon_cols).fillna(0.0)
            df_heads[isochrone] = head_series.reindex(self.heads_cols).fillna(0.0)

        # Totales + redondeos
        df_tonnage, df_heads = self._add_totals(df_tonnage, df_heads, self.flag)
        df_tonnage = np.round(df_tonnage, 1)
        df_heads = np.round(df_heads, 0)

        return df_tonnage, df_heads, gdf_isochrones

    # Mantén _add_totals aquí o herédalo de la base
    def _add_totals(self, df_tonnage, df_heads, country: str = "spain"):
        config = self.constants
        TONNAGECOWSLURRY = config.get("dataset_columns", {}).get("TONNAGECOWSLURRY")
        TONNAGECOWMANURE = config.get("dataset_columns", {}).get("TONNAGECOWMANURE")
        SHEEPGOATMANURE = config.get("dataset_columns", {}).get("SHEEPGOATMANURE")
        CROPS = config.get("dataset_columns", {}).get("crops")

        tonnageCowSlurry = [c for c in self.kTon_cols if any(sub in c for sub in TONNAGECOWSLURRY)]
        headsCowSlurry   = [c for c in self.heads_cols if any(sub in c for sub in TONNAGECOWSLURRY)]
        totalCowSlurryT  = pd.DataFrame(df_tonnage.loc[tonnageCowSlurry].sum()).T; totalCowSlurryT.index = ["Total Cow Slurry (kTon)"]
        totalCowSlurryH  = pd.DataFrame(df_heads.loc[headsCowSlurry].sum()).T;   totalCowSlurryH.index = ["Total Cow Slurry (no. heads)"]

        cowManureTonnage = [c for c in self.kTon_cols if any(sub in c for sub in TONNAGECOWMANURE)]
        cowManureHeads   = [c for c in self.heads_cols if any(sub in c for sub in TONNAGECOWMANURE)]
        totalCowManureT  = pd.DataFrame(df_tonnage.loc[cowManureTonnage].sum()).T; totalCowManureT.index = ["Total Cow Manure (kTon)"]
        totalCowManureH  = pd.DataFrame(df_heads.loc[cowManureHeads].sum()).T;   totalCowManureH.index = ["Total Cow Manure (no. heads)"]

        sheepGoatsTonnage = [c for c in self.kTon_cols if any(sub in c for sub in SHEEPGOATMANURE)]
        sheepGoatsHeads   = [c for c in self.heads_cols if any(sub in c for sub in SHEEPGOATMANURE)]
        totalSheepGoatsT  = pd.DataFrame(df_tonnage.loc[sheepGoatsTonnage].sum()).T; totalSheepGoatsT.index = ["Total Sheep & Goats Manure (kTon)"]
        totalSheepGoatsH  = pd.DataFrame(df_heads.loc[sheepGoatsHeads].sum()).T;   totalSheepGoatsH.index = ["Total Sheep & Goats (no. heads)"]

        cropTonnage = CROPS
        totalCropsT = pd.DataFrame(df_tonnage.loc[cropTonnage].sum()).T; totalCropsT.index = ["Total Crops (ktn)"]

        df_tonnage = pd.concat([df_tonnage, totalCowSlurryT, totalCowManureT, totalSheepGoatsT, totalCropsT])
        df_heads   = pd.concat([df_heads, totalCowSlurryH, totalCowManureH, totalSheepGoatsH])

        FINALTONNAGECOLS = config.get("dataset_columns", {}).get("FINALTONNAGECOLS").keys()
        FINALHEADSCOLS   = config.get("dataset_columns", {}).get("FINALHEADSCOLS")

        df_tonnage = df_tonnage.loc[FINALTONNAGECOLS]
        df_heads   = df_heads.loc[FINALHEADSCOLS]
        return df_tonnage, df_heads
