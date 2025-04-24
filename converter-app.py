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

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Coordinates → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste coordinates below to generate a KML polygon, view it on a map, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input ---
raw_input = st.text_area(
    "Coordinates:",
    placeholder="Example: LAT...LON 3906 10399 3924 10393 3921 10357 3902 10361",
    height=150,
    key="coord_input"
)

# --- Parse Function ---
def parse_coords(text):
    tokens = re.findall(r'\d+', text)
    coords = []
    i = 0
    while i < len(tokens) - 1:
        try:
            lat = int(tokens[i]) / 100.0
            lon = -int(tokens[i + 1]) / 100.0
            coords.append((lon, lat))  # folium and KML use (lon, lat)
        except ValueError:
            pass
        i += 2
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

# --- Population Calculation from GeoJSON ---
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
generate_clicked = st.button("Generate KML", use_container_width=True)

if generate_clicked:
    if raw_input.strip():
        parsed_coords = parse_coords(raw_input)
        if len(parsed_coords) < 4:
            st.error("Not enough points to form a polygon.")
        else:
            st.session_state["coords"] = parsed_coords
    else:
        st.warning("Please enter some coordinates.")

# --- Results ---
if "coords" in st.session_state:
    coords = st.session_state["coords"]

    # --- KML Generation ---
    kml = simplekml.Kml()
    kml.newpolygon(name="My Polygon", outerboundaryis=coords)
    kml_bytes = kml.kml().encode("utf-8")

    # --- GeoJSON Generation ---
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

    # --- Download Buttons (Side-by-Side) ---
    col1, col2, col3 = st.columns([1, 1, 1])
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

    # --- Map Preview ---
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    lon_center = sum([pt[0] for pt in coords]) / len(coords)
    lat_center = sum([pt[1] for pt in coords]) / len(coords)
    m = folium.Map(location=[lat_center, lon_center], zoom_start=9, tiles="CartoDB positron")
    folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color="blue", fill=True).add_to(m)
    st_folium(m, width=700, height=500)

    # --- Population Estimation ---
    raster_path = "data/landscan-global-2023.tif"  # Update if renamed
    population = estimate_population_from_coords(coords, raster_path)

    if population is not None:
        st.markdown("<h4 style='text-align: center;'>Estimated Population</h4>", unsafe_allow_html=True)
        st.success(f"Estimated Population: {population:,.0f}")
        st.caption("Note: LandScan represents ambient population (24-hour average).")

# --- Attribution ---
st.markdown("---")
st.markdown(
    "<p style='font-size: 0.8rem; text-align: center; color: grey;'>Population data © Oak Ridge National Laboratory. "
    "Distributed under <a href='https://creativecommons.org/licenses/by/4.0/' target='_blank'>CC BY 4.0</a>.</p>",
    unsafe_allow_html=True
)
