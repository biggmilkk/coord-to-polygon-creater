import streamlit as st
import simplekml
import folium
import re
import geopandas as gpd
from rasterstats import zonal_stats
from streamlit_folium import st_folium
import tempfile
import os
import json
from shapely.geometry import Polygon

# Version: v2318.24.4.2025

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

# --- Session state setup for delayed rerun ---
if "rerun_done" not in st.session_state:
    st.session_state["rerun_done"] = False

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Coordinates → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste coordinates below to generate a polygon, preview it on a map, download KML & GeoJSON, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input ---
raw_input = st.text_area(
    "Coordinates:",
    placeholder="Example: 34.2482, -98.6066\n34° 14' 53.52'' N 98° 36' 23.76'' W",
    height=150,
    key="coord_input"
)

# --- Coordinate Parsers ---
def dms_to_dd(deg, min_, sec, direction):
    dd = float(deg) + float(min_) / 60 + float(sec) / 3600
    return -dd if direction.upper() in ["S", "W"] else dd

def ddm_to_dd(deg, min_, direction):
    dd = float(deg) + float(min_) / 60
    return -dd if direction.upper() in ["S", "W"] else dd

def parse_coords(text):
    text = text.replace(",", " ").replace("′", "'").replace("''", "\"").replace("“", "\"").replace("”", "\"")
    coords = []
    i = 0

    dms_pattern = re.compile(r"(\d+)°\s*(\d+)'[\s]*([\d.]+)(?:\"|''|″)?\s*([NSEW])", re.IGNORECASE)
    ddm_pattern = re.compile(r"(\d+)°\s*([\d.]+)'\s*([NSEW])", re.IGNORECASE)

    dms_matches = dms_pattern.findall(text)
    ddm_matches = ddm_pattern.findall(text)

    if dms_matches and len(dms_matches) % 2 == 0:
        for j in range(0, len(dms_matches), 2):
            lat = dms_to_dd(*dms_matches[j])
            lon = dms_to_dd(*dms_matches[j + 1])
            coords.append((lon, lat))
        return coords

    if ddm_matches and len(ddm_matches) % 2 == 0:
        for j in range(0, len(ddm_matches), 2):
            lat = ddm_to_dd(*ddm_matches[j])
            lon = ddm_to_dd(*ddm_matches[j + 1])
            coords.append((lon, lat))
        return coords

    tokens = re.findall(r'-?\d+\.?\d*', text)
    while i < len(tokens) - 1:
        try:
            lat = float(tokens[i])
            lon = float(tokens[i + 1])
            if abs(lat) > 90:
                lat = lat / 100.0
            if abs(lon) > 180:
                lon = -abs(lon / 100.0)
            coords.append((lon, lat))
        except ValueError:
            pass
        i += 2

    return coords

# --- Canada Check ---
def is_polygon_in_canada(coords):
    try:
        poly = Polygon(coords)
        centroid = poly.centroid
        return (
            41.0 <= centroid.y <= 83.0 and
            -141.0 <= centroid.x <= -52.0
        )
    except:
        return False

# --- Population Estimation ---
def estimate_population_from_coords(coords, raster_path):
    try:
        poly_geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {}
            }]
        }

        with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson", mode="w") as tmp:
            gdf = gpd.GeoDataFrame.from_features(poly_geojson["features"])
            gdf.to_file(tmp.name, driver="GeoJSON")
            tmp_path = tmp.name

        stats = zonal_stats(tmp_path, raster_path, stats=["sum"])
        os.unlink(tmp_path)
        return stats[0]["sum"]
    except Exception as e:
        st.error(f"Error estimating population: {e}")
        return None

# --- Generate Button ---
generate_clicked = st.button("Generate Map", use_container_width=True)

# --- Parse and Store Coordinates ---
if generate_clicked:
    if raw_input.strip():
        parsed_coords = parse_coords(raw_input)
        if len(parsed_coords) < 3:
            st.error(f"Only detected {len(parsed_coords)} valid points — need at least 3 to form a polygon.")
            st.session_state.pop("coords", None)  # Clear previous results
        else:
            if parsed_coords[0] != parsed_coords[-1]:
                parsed_coords.append(parsed_coords[0])
            st.session_state["coords"] = parsed_coords
    else:
        st.warning("Please enter some coordinates.")
        st.session_state.pop("coords", None)  # Clear previous results

# --- Main Output ---
if "coords" in st.session_state:
    coords = st.session_state["coords"]

    # KML
    kml = simplekml.Kml()
    kml.newpolygon(name="My Polygon", outerboundaryis=coords)
    kml_bytes = kml.kml().encode("utf-8")

    # GeoJSON
    geojson_data = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {}
        }]
    }
    geojson_bytes = json.dumps(geojson_data, indent=2).encode("utf-8")

    # --- Downloads ---
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download KML",
            data=kml_bytes,
            file_name="polygon.kml",
            mime="application/vnd.google-earth.kml+xml",
            use_container_width=True
        )
    with col2:
        st.download_button(
            label="Download GeoJSON",
            data=geojson_bytes,
            file_name="polygon.geojson",
            mime="application/geo+json",
            use_container_width=True
        )

    # --- Population Estimate ---
    if is_polygon_in_canada(coords):
        raster_path = "data/canada-population-2023.tif"
        pop_label = "Estimated Population (Canada):"
    else:
        raster_path = "data/landscan-global-2023.tif"
        pop_label = "Estimated Population (Global):"

    population = estimate_population_from_coords(coords, raster_path)
    if population is not None:
        st.success(f"{pop_label} {population:,.0f}")
        st.markdown(
            "<p style='text-align: center; font-size: 0.85rem; color: grey;'>Population data is an ambient (24-hour average) estimate.</p>",
            unsafe_allow_html=True
        )

    # --- Map Preview ---
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    bounds = [(lat, lon) for lon, lat in coords]
    m = folium.Map(tiles="CartoDB positron")
    folium.Polygon(locations=bounds, color="blue", fill=True).add_to(m)
    m.fit_bounds(bounds)
    returned_map = st_folium(m, width=700, height=400)

    # --- Rerun Once to Fix Blank Space Bug ---
    if not st.session_state["rerun_done"]:
        st.session_state["rerun_done"] = True
        st.experimental_rerun()
