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
from xml.etree import ElementTree as ET
import zipfile
from io import BytesIO

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
st.markdown("<h2 style='text-align: center;'>Multi-Polygon Map Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Upload KML/KMZ/GeoJSON files or paste coordinates to generate polygons on a map, download them, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input Switch ---
input_mode = st.radio("Choose Input Method", ["Paste Coordinates", "Upload a Map File"], horizontal=True)

# --- Paste Coordinates ---
if input_mode == "Paste Coordinates":
    st.text_area(
        "Coordinates:",
        placeholder="Example: 3361 10227 3383 10224 3383 10167 3342 10176",
        height=150,
        key="coord_input"
    )

# --- File Upload ---
uploaded_file = None
if input_mode == "Upload a Map File":
    uploaded_file = st.file_uploader("Upload Polygon File (KML, KMZ, GeoJSON, JSON)", type=["kml", "kmz", "geojson", "json"])

# --- Clean session ---
if input_mode == "Upload a Map File" and uploaded_file is None and st.session_state["file_was_uploaded"]:
    for key in ["coords", "file_was_uploaded", "rerun_done"]:
        st.session_state.pop(key, None)
    st.rerun()
elif input_mode == "Paste Coordinates" and not st.session_state.get("coord_input", "").strip():
    st.session_state.pop("coords", None)

# --- Parsers ---
def parse_coords(text):
    tokens = re.findall(r'-?\d+\.?\d*', text.replace(',', ' '))
    coords = []
    i = 0
    while i < len(tokens) - 1:
        try:
            lat = float(tokens[i])
            lon = float(tokens[i + 1])
            coords.append((lon, lat))
        except ValueError:
            pass
        i += 2
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return [coords] if coords else []

def extract_coords_from_kml_string(kml_string):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    root = ET.fromstring(kml_string)
    polygons = []
    for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
        coords = []
        raw_coords = coord_text.text.strip().split()
        for coord in raw_coords:
            parts = coord.split(',')
            if len(parts) >= 2:
                lon, lat = map(float, parts[:2])
                coords.append((lon, lat))
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if coords:
            polygons.append(coords)
    return polygons

def extract_coords_from_kmz(file_bytes):
    with zipfile.ZipFile(BytesIO(file_bytes)) as kmz:
        for name in kmz.namelist():
            if name.endswith(".kml"):
                kml_string = kmz.read(name).decode("utf-8")
                return extract_coords_from_kml_string(kml_string)
    return []

# --- Population Estimation ---
def estimate_population_from_coords(multi_coords, raster_path):
    try:
        features = []
        for coords in multi_coords:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {}
            })
        poly_geojson = {"type": "FeatureCollection", "features": features}
        with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson", mode="w") as tmp:
            gdf = gpd.GeoDataFrame.from_features(poly_geojson["features"])
            gdf.to_file(tmp.name, driver="GeoJSON")
            tmp_path = tmp.name
        stats = zonal_stats(tmp_path, raster_path, stats=["sum"])
        os.unlink(tmp_path)
        return sum(s["sum"] for s in stats if s["sum"] is not None)
    except Exception as e:
        st.error(f"Error estimating population: {e}")
        return None

# --- Generate Button ---
if st.button("Generate Map", use_container_width=True):
    st.session_state["generate_trigger"] = True

# --- Main Processing ---
if st.session_state.get("generate_trigger"):
    all_polygons = []
    if input_mode == "Paste Coordinates":
        text = st.session_state.get("coord_input", "")
        all_polygons = parse_coords(text)
    elif input_mode == "Upload a Map File" and uploaded_file:
        file_type = uploaded_file.name.split('.')[-1].lower()
        if file_type in ["geojson", "json"]:
            geojson = json.load(uploaded_file)
            features = geojson["features"] if geojson["type"] == "FeatureCollection" else [geojson]
            for feature in features:
                geom = feature["geometry"]
                if geom["type"].lower() == "polygon":
                    coords = geom["coordinates"][0]
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    all_polygons.append(coords)
                elif geom["type"].lower() == "multipolygon":
                    for part in geom["coordinates"]:
                        coords = part[0]
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        all_polygons.append(coords)
        elif file_type == "kml":
            doc = uploaded_file.read().decode("utf-8")
            all_polygons = extract_coords_from_kml_string(doc)
        elif file_type == "kmz":
            all_polygons = extract_coords_from_kmz(uploaded_file.read())

    if all_polygons:
        st.session_state["coords"] = all_polygons
        st.session_state["file_was_uploaded"] = True
    else:
        st.warning("No valid polygons found.")
    st.session_state["generate_trigger"] = False

# --- Output ---
if st.session_state.get("coords"):
    polygons = st.session_state["coords"]

    # Downloads
    kml = simplekml.Kml()
    for i, poly in enumerate(polygons):
        kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=poly)

    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [poly]}, "properties": {}} for poly in polygons
        ]
    }

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download KML", kml.kml().encode("utf-8"), file_name="polygons.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
    with col2:
        st.download_button("Download GeoJSON", json.dumps(geojson_data, indent=2).encode("utf-8"), file_name="polygons.geojson", mime="application/geo+json", use_container_width=True)

    # Population
    raster_path = "data/landscan-global-2023.tif"
    population = estimate_population_from_coords(polygons, raster_path)
    if population is not None:
        st.success(f"Estimated Population: {population:,.0f}")

    # Map
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    m = folium.Map(tiles="CartoDB positron")
    all_points = []
    for poly in polygons:
        latlons = [(lat, lon) for lon, lat in poly]
        folium.Polygon(locations=latlons, color="blue", fill=True).add_to(m)
        all_points.extend(latlons)

    if all_points:
        m.fit_bounds(all_points)
    st_folium(m, width=700, height=400)

    if not st.session_state["rerun_done"]:
        st.session_state["rerun_done"] = True
        st.rerun()
