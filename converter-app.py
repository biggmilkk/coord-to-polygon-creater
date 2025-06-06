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
from fastkml import kml as fastkml

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

# --- Session defaults ---
for key, default in {
    "rerun_done": False,
    "coords": None,
    "generate_trigger": False,
    "file_was_uploaded": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Coordinates → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste coordinates or upload a polygon file to generate a map, download KML/GeoJSON, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input Method Switch ---
input_mode = st.radio("Choose Input Method", ["Paste Coordinates", "Upload a Map File"], horizontal=True)

# --- Coordinate Input UI ---
if input_mode == "Paste Coordinates":
    st.text_area(
        "Coordinates:",
        placeholder="Example: 3361 10227 3383 10224 3383 10167 3342 10176",
        height=150,
        key="coord_input"
    )

# --- File Upload UI ---
uploaded_file = None
if input_mode == "Upload a Map File":
    uploaded_file = st.file_uploader("Upload Polygon File (KML or GeoJSON)", type=["kml", "geojson"])

# --- Clear data if switching modes or removing input ---
if input_mode == "Upload a Map File" and uploaded_file is None and st.session_state["file_was_uploaded"]:
    for key in ["coords", "file_was_uploaded", "rerun_done"]:
        st.session_state.pop(key, None)
    st.rerun()
elif input_mode == "Paste Coordinates" and not st.session_state.get("coord_input", "").strip():
    st.session_state.pop("coords", None)

# --- Coordinate Parsing ---
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
            if lat > 90 and lon > 180:
                lat = lat / 100.0
                lon = lon / 100.0
                lon = -abs(lon)
            coords.append((lon, lat))
        except ValueError:
            pass
        i += 2
    return coords

def dms_to_dd(deg, min_, sec, direction):
    dd = float(deg) + float(min_) / 60 + float(sec) / 3600
    return -dd if direction.upper() in ["S", "W"] else dd

def ddm_to_dd(deg, min_, direction):
    dd = float(deg) + float(min_) / 60
    return -dd if direction.upper() in ["S", "W"] else dd

# --- Population Estimation ---
def estimate_population_from_coords(coords, raster_path):
    try:
        poly_geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
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
if st.button("Generate Map", use_container_width=True):
    st.session_state["generate_trigger"] = True

# --- Main Logic for Each Mode ---
if st.session_state.get("generate_trigger"):

    # --- From Coordinates ---
    if input_mode == "Paste Coordinates":
        text = st.session_state.get("coord_input", "")
        if text.strip():
            parsed_coords = parse_coords(text)
            if len(parsed_coords) < 3:
                st.error("At least 3 coordinate pairs are required to form a polygon.")
                st.session_state.pop("coords", None)
            else:
                if parsed_coords[0] != parsed_coords[-1]:
                    parsed_coords.append(parsed_coords[0])
                st.session_state["coords"] = parsed_coords
                st.session_state["file_was_uploaded"] = False

    # --- From Uploaded File ---
    elif input_mode == "Upload a Map File" and uploaded_file:
        file_type = uploaded_file.name.split('.')[-1].lower()
        uploaded_coords = None
        try:
            if file_type == "geojson":
                geojson = json.load(uploaded_file)
                feature = geojson["features"][0] if geojson["type"] == "FeatureCollection" else geojson
                geometry = feature["geometry"]
                if geometry["type"].lower() == "polygon":
                    uploaded_coords = geometry["coordinates"][0]
            elif file_type == "kml":
                doc = uploaded_file.read().decode("utf-8")
                k = fastkml.KML()
                k.from_string(doc)
                for document in k.features:  # ✅ Correct: no parentheses
                    for feature in document.features:  # ✅ Correct
                        if hasattr(feature, 'geometry') and feature.geometry:
                            geom = feature.geometry
                            if hasattr(geom, "exterior") and geom.exterior:
                                uploaded_coords = list(geom.exterior.coords)
                                break
                    if uploaded_coords:
                        break

            if uploaded_coords:
                if uploaded_coords[0] != uploaded_coords[-1]:
                    uploaded_coords.append(uploaded_coords[0])
                st.session_state["coords"] = uploaded_coords
                st.session_state["file_was_uploaded"] = True
                st.success("Polygon loaded from uploaded file.")

        except Exception as e:
            st.error(f"Failed to parse file: {e}")

    st.session_state["generate_trigger"] = False

# --- Output ---
if st.session_state.get("coords"):
    coords = st.session_state["coords"]

    # Downloads
    kml = simplekml.Kml()
    kml.newpolygon(name="My Polygon", outerboundaryis=coords)
    geojson_data = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {}
        }]
    }

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download KML", kml.kml().encode("utf-8"),
                           file_name="polygon.kml", mime="application/vnd.google-earth.kml+xml",
                           use_container_width=True)
    with col2:
        st.download_button("Download GeoJSON", json.dumps(geojson_data, indent=2).encode("utf-8"),
                           file_name="polygon.geojson", mime="application/geo+json",
                           use_container_width=True)

    # Population
    raster_path = "data/landscan-global-2023.tif"
    population = estimate_population_from_coords(coords, raster_path)
    if population is not None:
        st.success(f"Estimated Population: {population:,.0f}")
        st.markdown(
            "<p style='text-align: center; font-size: 0.85rem; color: grey;'>LandScan represents ambient population (24-hour average).</p>",
            unsafe_allow_html=True
        )

    # Map
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    m = folium.Map(tiles="CartoDB positron")
    latlons = [(lat, lon) for lon, lat in coords]
    folium.Polygon(locations=latlons, color="blue", fill=True).add_to(m)
    m.fit_bounds(latlons)
    st_folium(m, width=700, height=400)

    if not st.session_state["rerun_done"]:
        st.session_state["rerun_done"] = True
        st.rerun()
