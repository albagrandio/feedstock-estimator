import os
from dotenv import load_dotenv
import requests
import pandas as pd
import geopandas as gpd
import numpy as np
import streamlit as st
import folium
from streamlit_folium import folium_static
from PIL import Image
from shapely.geometry.polygon import Polygon
from shapely.geometry import mapping
from shapely.ops import transform
import json
import io, zipfile
from io import BytesIO
import urllib, json
import plotly.graph_objects as go
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import hashlib, colorsys, random
from typing import List, Dict, Any
import yaml

from src.constants import LOGO_TAB_PATH, bolded_totals


# Load environment variables from the .env file
load_dotenv()

# Access the API key
api_key = os.getenv("API_KEY")
mapbox_token = os.getenv("MAPBOX_TOKEN")
bingkey = os.getenv("BING_KEY")


def update_flag(flag):
    st.session_state["flag"] = flag


def load_constants(country: str, file_path: str = "src/country_config.yaml") -> dict:
    """
    Load constants from a YAML file for a specific country.

    Args:
        country (str): The country to filter constants for.
        file_path (str): Path to the YAML file.

    Returns:
        dict: Constants for the specified country.
    """
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)

    # Extract and return constants for the given country
    # Retrieve configuration for the country
    country_config: dict = data.get("countries", {}).get(country, {})
    return country_config


def generate_color_for_product(product_name: str) -> List[int]:
    """Generate a consistent color for a product name using hashing."""
    product_str = str(product_name)
    if product_str is None:
        print(product_str)
        return [200, 200, 200]

    try:
        # Use evenly spaced hues based on index
        random.seed(str(product_name))
        hue = random.random()  #
        saturation = 0.7
        value = 0.95

        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        return [int(c * 255) for c in rgb]
    except Exception as e:
        print(f"Error generating color for {product_name}: {e}")
        return [200, 200, 200]


# Function to convert Folium map to image
def map_to_image(m):
    img_data = m._to_png(5)
    img = Image.open(io.BytesIO(img_data))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr


def create_pdf_from_image(image_bytes):
    image = Image.open(BytesIO(image_bytes))
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer)

    # Get the dimensions of the image
    width, height = image.size

    # Draw the image on the canvas
    c.drawImage(ImageReader(image), 0, 0, width, height)
    c.showPage()
    c.save()

    # Get the PDF data
    pdf_data = pdf_buffer.getvalue()
    pdf_buffer.close()
    return pdf_data


def create_zip_file():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Add first DataFrame as CSV
        df1 = st.session_state.df_tonnage
        zip_file.writestr("df_tonnage1.csv", df1.to_csv(index=True))

        # Add second DataFrame as CSV
        df2 = st.session_state.df_heads
        zip_file.writestr("df_heads.csv", df2.to_csv(index=True))

        # Add third DataFrame as CSV
        gdf_isochrones = st.session_state.gdf_isochrones
        # Convert to GeoJSON-compatible dictionary
        geojson_dict = {"type": "FeatureCollection", "features": []}

        for idx, row in gdf_isochrones.iterrows():
            feature = {
                "type": "Feature",
                "geometry": mapping(row.geometry),
                "properties": {col: row[col] for col in gdf_isochrones.columns if col != "geometry"},
            }
            geojson_dict["features"].append(feature)

        geojson_str = json.dumps(geojson_dict)
        zip_file.writestr("isochrones.geojson", geojson_str)

        zip_file.writestr("map.html", st.session_state["map"])

        # Add second map HTML (PyDeck)
        # Generate PyDeck map HTML
        if st.session_state["plotly_map"] is not None:
            zip_file.writestr("plotly_map.html", st.session_state["plotly_map"])

    return zip_buffer.getvalue()


def validate_coordinates(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return False, "Coordinates must be numeric values."

    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90 degrees."

    if not (-180 <= lon <= 180):
        return False, "Longitude must be between -180 and 180 degrees."

    return True, "Valid coordinates."


def calculate_mapbox_isochrone_distance_time(longitude, latitude, distances=None, times=None):
    """
    Function to calculate the isochrone from a specified location.
    The function uses Bing maps API and requires set up of the KEY param:
    https://learn.microsoft.com/en-us/bingmaps/rest-services/routes/calculate-an-isochrone
    Input: location specified by longitude and latitude; distances or times to specified isochrone boundary
    Output: polygon of isochrone
    """

    # Define the URL for the Mapbox Isochrone API with the truck driving profile
    # isochrone_url = f"https://api.mapbox.com/isochrone/v1/mapbox/driving/{center_point[0]},{center_point[1]}"

    BASE = "https://api.mapbox.com/isochrone/v1/mapbox/"

    longitude = st.session_state.lng
    latitude = st.session_state.lat

    address = f"{longitude},{latitude}"
    travel_mode = "driving-traffic/"

    params = {
        #'alternatives': "true",
        "polygons": "true",  # Return the result as polygons
        "access_token": mapbox_token,  # Your Mapbox API token
    }

    if distances and times:
        raise ValueError("Invalid inputs. Specify either maximum distance or time, not both.")
    elif distances:
        print(distances)

        # Set parameters for the API call
        params["contours_meters"] = distances
        print("Calculating " + str(distances) + "km isochrone.")
    elif times:
        params["contours_minutes"] = times
        print("Calculating " + str(times) + " minute isochrone with no traffic effects.")
    else:
        raise ValueError("Invalid inputs. Specify either a maximum distance or time.")

    isochrone_url = f"{BASE + travel_mode +address}"
    print(isochrone_url)
    print(st.session_state.lng)
    print(st.session_state.lat)

    response = requests.get(isochrone_url, params=params)
    print(response)
    print(params)

    if response.status_code != 200:
        print("Unsuccessful Request: ", response)

        raise requests.HTTPError("Unsuccessful Request: ", response)

    isochrone_data = response.json()  # Parse the JSON response
    print(json.dumps(isochrone_data, indent=2))  # Print the isochrone data in a readable format

    for feature in isochrone_data["features"]:
        print(feature["geometry"]["coordinates"])

        coordinates = feature["geometry"]["coordinates"][0]  # Get the outer ring of the first polygon
        iso = Polygon(coordinates)

    return iso


def calculate_bing_isochrone_distance_time(longitude, latitude, distances=None, times=None):
    """
    Function to calculate the isochrone from a specified location.
    The function uses Bing maps API and requires set up of the KEY param:
    https://learn.microsoft.com/en-us/bingmaps/rest-services/routes/calculate-an-isochrone
    Input: location specified by longitude and latitude; distances or times to specified isochrone boundary
    Output: polygon of isochrone
    """

    BASE = "https://dev.virtualearth.net"
    GEOCODE_PATH = "/REST/v1/Routes/Isochrones?"
    ## Uncomment and insert API key below
    KEY = bingkey

    address = str(latitude) + "," + str(longitude)
    travel_mode = "truck"

    params = {
        "waypoint": address,
        "travelMode": travel_mode,
    }

    if distances and times:
        raise ValueError("Invalid inputs. Specify either maximum distance or time, not both.")
    elif distances:
        params["distanceUnit"] = "km"
        params["optimize"] = "distance"
        params["maxDistance"] = distances
        print("Calculating " + str(distances) + "km isochrone.")
    elif times:
        params["timeUnit"] = "minute"
        params["optimize"] = "time"  # currently no traffic effect
        params["maxTime"] = times
        print("Calculating " + str(times) + " minute isochrone with no traffic effects.")
    else:
        raise ValueError("Invalid inputs. Specify either a maximum distance or time.")

    path = GEOCODE_PATH + urllib.parse.urlencode(params)
    url = BASE + path + "&key=" + KEY

    response = requests.get(url)
    result = json.loads(response.text)
    response.close()

    if response.status_code != 200:
        raise requests.HTTPError("Unsuccessful Request: ", response)

    result_coordinates = result["resourceSets"][0]["resources"][0]["polygons"][0]["coordinates"][0]

    result_polygons = Polygon(result_coordinates)
    result_polygons = transform(lambda x, y: (y, x), result_polygons)  # flip latitutde and longitude

    return result_polygons


def calculate_isochrones(longitude, latitude, distances=None, times=None):
    """
    Function to calculate isochrones centered at the specified location in
    specified driving time or distance.
    Input: longitude, latitude of the location
    distances = list of kms
    times = list of minutes
    Output: geodataframe containing isochrones for each specified km and/or mins
    """

    # initialise empty geodataframe
    gdf_iso = gpd.GeoDataFrame(columns=["isochrone", "geometry"], geometry="geometry")

    # calculate distance isochrones for each km
    for km in distances:

        # km = km *1000
        # calculate the isochrone
        iso = calculate_bing_isochrone_distance_time(longitude, latitude, distances=km)
        # initialise temporary geodataframe
        gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
        # add detail of isochrone distance
        gdf_iso_temp["isochrone"] = str(int(km)) + " km"
        # concatentate temporary geodataframe to master
        gdf_iso = pd.concat([gdf_iso, gdf_iso_temp])

    # calculate time isochrones for each min
    for mins in times:
        # calculate the isochrone
        iso = calculate_bing_isochrone_distance_time(longitude, latitude, times=mins)
        # initialise temporary geodataframe
        gdf_iso_temp = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[iso])
        # add detail of isochrone time
        gdf_iso_temp["isochrone"] = str(int(mins)) + " mins"
        # concatentate temporary geodataframe to master
        gdf_iso = pd.concat([gdf_iso, gdf_iso_temp])

    return gdf_iso


def browser_tab_title(page_title: str) -> None:
    """Set the browser tab title and favicon.

    Args:
        page_title (str): The title to display in the browser tab.

    Returns:
        None
    """
    st.set_page_config(
        page_title=page_title,
        page_icon=Image.open(LOGO_TAB_PATH),
        initial_sidebar_state="expanded",
        layout="wide",
    )


def is_in_lombardy(latitude: float, longitude: float) -> bool:
    """
    Check if a given latitude and longitude are within the Lombardy region of Italy

    Parameters:
    latitude (float): Latitude coordinate
    longitude (float): Longitude coordinate
    mapbox_token (str): Mapbox API access token

    Returns:
    bool: True if the coordinates are in Lombardy, False otherwise
    """
    access_token = mapbox_token
    base_url = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    url = f"{base_url}/{longitude},{latitude}.json"
    params = {"access_token": access_token, "types": "region", "language": "en"}  # Limit to region level results

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data["features"]:
            lombardy_provinces = [
                "Bergamo",
                "Brescia",
                "Como",
                "Cremona",
                "Lecco",
                "Lodi",
                "Mantua",
                "Milan",
                "Monza and Brianza",
                "Pavia",
                "Sondrio",
                "Varese",
            ]

            # Also check for Italian names
            lombardy_provinces_it = [
                "Bergamo",
                "Brescia",
                "Como",
                "Cremona",
                "Lecco",
                "Lodi",
                "Mantova",
                "Milano",
                "Monza e Brianza",
                "Pavia",
                "Sondrio",
                "Varese",
            ]

            for feature in data["features"]:
                # Check if it's directly mentioning Lombardy
                if "Lombardy" in feature.get("text", "") or "Lombardia" in feature.get("text", ""):
                    return True

                # Check if it's one of the provinces in Lombardy
                province_name = feature.get("text", "")
                if province_name in lombardy_provinces or province_name in lombardy_provinces_it:
                    return True

                # Check if features have short_code property (for provinces)
                if feature.get("properties", {}).get("short_code", "").startswith("IT-"):
                    province_code = feature.get("properties", {}).get("short_code", "")
                    # Lombardy province codes: IT-BG, IT-BS, IT-CO, IT-CR, IT-LC, IT-LO, IT-MN, IT-MI, IT-MB, IT-PV, IT-SO, IT-VA
                    lombardy_province_codes = [
                        "IT-BG",
                        "IT-BS",
                        "IT-CO",
                        "IT-CR",
                        "IT-LC",
                        "IT-LO",
                        "IT-MN",
                        "IT-MI",
                        "IT-MB",
                        "IT-PV",
                        "IT-SO",
                        "IT-VA",
                    ]
                    if province_code in lombardy_province_codes:
                        return True

            # If we've gone through all features and haven't found a match, do a broader search
            for feature in data["features"]:
                place_name = feature.get("place_name", "").lower()
                if "lombardy" in place_name or "lombardia" in place_name:
                    return True

            return False
        else:
            return False

    else:
        print(f"Error: {response.status_code}")
        return False


def reverse_geocode(latitude, longitude):
    access_token = mapbox_token
    base_url = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    # url = f"{base_url}/{longitude},{latitude}.json?access_token={access_token}"
    url = f"{base_url}/{longitude},{latitude}.json"
    params = {"access_token": access_token}

    response = requests.get(url, params=params)

    # response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data["features"]:
            # The first feature is typically the most relevant
            address = data["features"][0]["place_name"]
            return address
        else:
            return False
    else:
        return False


def get_place_suggestions(input_text):
    if not mapbox_token:
        print("WARNING: MAPBOX_TOKEN environment variable is not set")
        return []
    endpoint = "https://api.mapbox.com/search/geocode/v6/forward"
    params = {
        "q": input_text,
        "access_token": mapbox_token,
        "autocomplete": "true",
        "country": "IT,ES",
        "limit": 5,
        "types": "place,locality,address,neighborhood",
    }
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        features = response.json().get("features", [])
        suggestions = [
            feature.get("properties", {}).get("full_address") or feature.get("properties", {}).get("name", "Unknown")
            for feature in features
        ]
        return suggestions
    else:
        print(f"Mapbox Geocoding API error: {response.status_code} - {response.text}")
        return []


def get_lat_long(location):
    if not mapbox_token:
        print("WARNING: MAPBOX_TOKEN environment variable is not set")
        return None, None
    base_url = "https://api.mapbox.com/search/geocode/v6/forward"
    params = {
        "q": location,
        "access_token": mapbox_token,
        "limit": 1,
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        features = response.json().get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]
            return coords[1], coords[0]  # lat, lng (Mapbox returns [lng, lat])
    else:
        print(f"Mapbox Geocoding API error: {response.status_code} - {response.text}")
    return None, None


def generate_mock_estimation(facility_type, address, distance, driving_time):
    # Your estimation logic here
    # This is where you'd implement your actual calculation based on the inputs

    # For demonstration, let's create some dummy data
    waste_data = {
        "WASTE TYPE": [
            "Cows (kTon)",
            "Dairy Cows (kTon)",
            "Suckler Cows (kTon)",
            "Replacement Cows (kTon)",
            "Sheep (kTon)",
            "Breeding Sheep (kTon)",
            "Fattening (kTon)",
        ],
        "10 KM": [0.6, 4.1, 4.1, 4.1, 0, 0, 0],
        "25 KM": [13.5, 12.1, 12.1, 12.1, 0, 0, 0],
        "30 KM": [20.6, 34.1, 34.1, 34.1, 0, 0, 0],
        "35 KM": [30.6, 56.1, 56.1, 56.1, 0, 0, 0],
        "40 KM": [40.6, 76.2, 76.2, 76.2, 0, 0, 0],
        "15 MIN": [0.6, 4.1, 4.1, 4.1, 0, 0, 0],
        "30 MIN": [13.5, 12.1, 12.1, 12.1, 0, 0, 0],
        "45 MIN": [20.6, 34.1, 34.1, 34.1, 0, 0, 0],
        "60 MIN": [30.6, 56.1, 56.1, 56.1, 0, 0, 0],
    }

    # Convert to DataFrame
    df = pd.DataFrame(waste_data)

    # Update the session state with the results
    st.session_state.estimation_results = df
    st.session_state.show_results = True


def show_results():
    st.subheader("Estimation Results")
    st.text(
        "123 Address Road Town, All facilities, 15 min, 30 min, 45 min, 60 m..."
    )  # we need to think about back optionality and how the user can go back and change the inputs

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Edit")
    with col2:
        st.button("Print")
    with col3:
        st.download_button(
            label="Download ⬇️",
            data=st.session_state.estimation_results.to_csv(index=False),
        )

    with st.expander("Waste metrics", expanded=True):
        st.dataframe(st.session_state.estimation_results)

    st.expander("Municipalities")
    st.expander("Feedstock Facilities")

    st.subheader("Map")
    m = folium.Map(location=[40.4168, -3.7038], zoom_start=11)
    folium.Marker([40.4168, -3.7038], tooltip="Madrid").add_to(m)
    folium_static(m)
