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

# Version: v2318.24.4.2025

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

if "rerun_done" not in st.session_state:
    st.session_state["rerun_done"] = False

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Coordinates → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste coordinates or upload a polygon file to generate a map, download KML/GeoJSON, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input ---
raw_input = st.text_area(
    "Coordinates:",
    placeholder="Example: 34.2482, -98.6066\n34° 14' 53.52'' N 98° 36' 23.76'' W",
    height=150,
    key="coord_input"
)

# --- File Upload ---
st.markdown("### Or Upload a KML/GeoJSON File")
uploaded_file = st.file_uploader("Upload Polygon File (KML or GeoJSON)", type=["kml", "geojson"])

# --- Clear everything if file is removed ---
if uploaded_file is None and "coords" in st.session_state:
    for key in ["coords", "rerun_done"]:
        st.session_state.pop(key, None)
    st.rerun()

uploaded_coords = None

if uploaded_file:
    file_type = uploaded_file.name.split('.')[-1].lower()

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
            features = list(k.features())
            placemarks = list(features[0].features())
            geom = placemarks[0].geometry
            uploaded_coords = list(geom.exterior.coords)

        if uploaded_coords:
            if uploaded_coords[0] != uploaded_coords[-1]:
                uploaded_coords.append(uploaded_coords[0])
            st.session_state["coords"] = uploaded_coords
            st.success("Polygon successfully loaded from uploaded file.")

    except Exception as e:
        st.error(f"Failed to parse file: {e}")

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

            # Heuristic: shorthand format like 3361 10227 → 33.61 -102.27
            if lat > 90 and lon > 180:
                lat = lat / 100.0
                lon = lon / 100.0
                lon = -abs(lon)

            coords.append((lon, lat))
        except ValueError:
            pass
        i += 2

    return coords

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

if generate_clicked:
    if raw_input.strip():
        parsed_coords = parse_coords(raw_input)
        if len(parsed_coords) < 3:
            st.error(f"Only detected {len(parsed_coords)} valid points — need at least 3 to form a polygon.")
            st.session_state.pop("coords", None)
        else:
            if parsed_coords[0] != parsed_coords[-1]:
                parsed_coords.append(parsed_coords[0])
            st.session_state["coords"] = parsed_coords
    elif not uploaded_file:
        st.warning("Please enter coordinates or upload a polygon file.")
        st.session_state.pop("coords", None)

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
    raster_path = "data/landscan-global-2023.tif"
    population = estimate_population_from_coords(coords, raster_path)
    if population is not None:
        st.success(f"Estimated Population: {population:,.0f}")
        st.markdown(
            "<p style='text-align: center; font-size: 0.85rem; color: grey;'>LandScan represents ambient population (24-hour average).</p>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='font-size: 0.8rem; text-align: center; color: grey;'>Population data © Oak Ridge National Laboratory. "
            "Distributed under <a href='https://creativecommons.org/licenses/by/4.0/' target='_blank'>CC BY 4.0</a>.</p>",
            unsafe_allow_html=True
        )

    # --- Map Preview ---
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    m = folium.Map(tiles="CartoDB positron")
    latlons = [(lat, lon) for lon, lat in coords]
    folium.Polygon(locations=latlons, color="blue", fill=True).add_to(m)
    m.fit_bounds(latlons)

    returned_map = st_folium(m, width=700, height=400)

    if not st.session_state["rerun_done"]:
        st.session_state["rerun_done"] = True
        st.rerun()
