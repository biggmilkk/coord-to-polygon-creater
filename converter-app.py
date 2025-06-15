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

#v0950.15.06.2925

st.set_page_config(page_title="Polygon Generator and Population Estimate", layout="centered")

# --- Session State Defaults ---
for key, default in {
    "coords": [],
    "generate_trigger": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Polygon Generator and Population Estimate</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Upload spatial data files or enter coordinates manually to visualize geographic areas on an interactive map. Define custom polygons and generate population estimates using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input Method ---
input_mode = st.radio("Choose Input Method", ["Paste Coordinates", "Upload Map Files"], horizontal=True)

# --- Coordinate Input ---
if input_mode == "Paste Coordinates":
    st.text_area(
        "Coordinates:",
        placeholder="Examples:\n4019 8042\n40.3167 -80.7000\n40°19′00″N 80°42′00″W",
        height=150,
        key="coord_input"
    )

# --- File Upload ---
uploaded_files = []
if input_mode == "Upload Map Files":
    uploaded_files = st.file_uploader("Upload Polygon Files (KML, KMZ, GeoJSON, JSON)", type=["kml", "kmz", "geojson", "json"], accept_multiple_files=True)

# --- Clean up if no input ---
if input_mode == "Upload Map Files" and not uploaded_files:
    st.session_state["coords"] = []
elif input_mode == "Paste Coordinates" and not st.session_state.get("coord_input", "").strip():
    st.session_state["coords"] = []

# --- Coordinate Parsing ---
def dm_to_dd(dm):
    degrees = int(dm // 100)
    minutes = dm % 100
    return round(degrees + minutes / 60, 6)

def dms_to_dd(degrees, minutes, seconds, direction):
    dd = degrees + minutes / 60 + seconds / 3600
    if direction in ['S', 'W']:
        dd *= -1
    return round(dd, 6)

def parse_coords(text):
    text = text.replace(',', ' ').replace(';', ' ')
    tokens = re.findall(r'[-+]?\d*\.\d+|[-+]?\d+', text.upper())
    coords = []

    # Try Decimal Degrees (DD)
    if len(tokens) >= 2:
        try:
            float_tokens = list(map(float, tokens))
            if all(-180 <= x <= 180 for x in float_tokens):
                i = 0
                while i < len(float_tokens) - 1:
                    lat, lon = float_tokens[i], float_tokens[i + 1]
                    if abs(lat) <= 90 and abs(lon) <= 180:
                        coords.append((lon, lat))
                        i += 2
                    else:
                        i += 1
                if coords and coords[0] != coords[-1]:
                    coords.append(coords[0])
                if coords:
                    return [coords]
        except:
            pass

    # Try DMS
    dms_pattern = re.findall(r'(\d+)[°:\s](\d+)[′:\s](\d+)[″\s]?([NSEW])', text.upper())
    if len(dms_pattern) >= 2:
        coords = []
        for i in range(0, len(dms_pattern) - 1, 2):
            try:
                lat_d, lat_m, lat_s, lat_dir = dms_pattern[i]
                lon_d, lon_m, lon_s, lon_dir = dms_pattern[i + 1]
                lat = dms_to_dd(int(lat_d), int(lat_m), int(lat_s), lat_dir)
                lon = dms_to_dd(int(lon_d), int(lon_m), int(lon_s), lon_dir)
                coords.append((lon, lat))
            except:
                continue
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if coords:
            return [coords]

    # Try DM (Lat Lon format, western hemisphere assumed)
    try:
        tokens = [int(token) for token in tokens if token.lstrip('-').isdigit()]
        i = 0
        while i < len(tokens) - 1:
            lat_dm = tokens[i]
            lon_dm = tokens[i + 1]
            if (lat_dm % 100) < 60 and (lon_dm % 100) < 60:
                lat = dm_to_dd(lat_dm)
                lon = -dm_to_dd(abs(lon_dm))  # assume Western Hemisphere
                coords.append((lon, lat))
            i += 2
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        if coords:
            return [coords]
    except:
        pass

    return []

# --- KML/KMZ Handlers ---
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

    with st.spinner("Processing input..."):
        if input_mode == "Paste Coordinates":
            text = st.session_state.get("coord_input", "")
            all_polygons = parse_coords(text)

        elif input_mode == "Upload Map Files" and uploaded_files:
            for uploaded_file in uploaded_files:
                file_type = uploaded_file.name.split('.')[-1].lower()
                try:
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
                        all_polygons.extend(extract_coords_from_kml_string(doc))
                    elif file_type == "kmz":
                        all_polygons.extend(extract_coords_from_kmz(uploaded_file.read()))
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")

    if all_polygons:
        st.session_state["coords"] = all_polygons
    else:
        st.session_state["coords"] = []
        st.warning("No valid polygons found.")
    st.session_state["generate_trigger"] = False

# --- Output ---
if st.session_state.get("coords"):
    polygons = st.session_state["coords"]

    with st.spinner("Generating map and estimating population..."):
        # --- ✅ Export KML ---
        kml = simplekml.Kml()
        for i, poly in enumerate(polygons):
            kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=poly)

        # --- ✅ Export GeoJSON ---
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

        # --- Population Estimate ---
        raster_path = "data/landscan-global-2023.tif"
        population = estimate_population_from_coords(polygons, raster_path)
        if population is not None:
            st.success(f"Estimated Population: {population:,.0f}")

        # --- Map Rendering ---
        st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
        m = folium.Map(tiles="CartoDB positron")
        all_points = []
        for poly in polygons:
            latlons = [(lat, lon) for lon, lat in poly]  # Flip to (lat, lon) for folium
            folium.Polygon(locations=latlons, color="blue", fill=True).add_to(m)
            all_points.extend(latlons)

        if all_points:
            m.fit_bounds(all_points)
        st_folium(m, width=700, height=400)
