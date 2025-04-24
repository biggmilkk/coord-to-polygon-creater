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
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste coordinates below (mixed formats allowed) to generate a polygon, preview it on a map, download KML & GeoJSON, and estimate population using LandScan data.</p>",
    unsafe_allow_html=True
)

# --- Input ---
raw_input = st.text_area(
    "Coordinates:",
    placeholder="Example: 34.2482, -98.6066\n34°14'53.52\"N 98°36'23.76\"W\n3424 9860",
    height=180,
    key="coord_input"
)

# --- Coordinate Parsers ---
def dms_to_dd(deg, min_, sec, direction):
    dd = float(deg) + float(min_) / 60 + float(sec) / 3600
    return -dd if direction.upper() in ["S", "W"] else dd

def ddm_to_dd(deg, min_, direction):
    dd = float(deg) + float(min_) / 60
    return -dd if direction.upper() in ["S", "W"] else dd

def auto_format_text(text):
    text = text.replace("′", "'").replace("″", "\"").replace("“", "\"").replace("”", "\"")
    text = text.replace("''", "\"")  # unify quote style

    # Add space before direction (e.g. 34.5N → 34.5 N)
    text = re.sub(r"(\d)([NSEW])", r"\1 \2", text, flags=re.IGNORECASE)

    # Add spacing between DMS units if missing (e.g. 34°14' → 34° 14')
    text = re.sub(r"(\d+)°(\d+)'", r"\1° \2'", text)
    text = re.sub(r"(\d+)'(\d+)", r"\1' \2", text)

    return text

def parse_coords(text):
    text = auto_format_text(text)
    tokens = re.findall(r"[^\s]+", text)
    coords = []
    skipped = []
    i = 0

    while i < len(tokens) - 1:
        pair = tokens[i:i+8]
        try:
            joined = " ".join(pair)

            # DMS match
            dms_matches = re.findall(r"(\d+)°\s*(\d+)'[\s]*([\d.]+)\"?\s*([NSEW])", joined, re.IGNORECASE)
            if len(dms_matches) >= 2:
                lat = dms_to_dd(*dms_matches[0])
                lon = dms_to_dd(*dms_matches[1])
                coords.append((lon, lat))
                i += 8
                continue

            # DDM match
            ddm_matches = re.findall(r"(\d+)°\s*([\d.]+)'\s*([NSEW])", joined, re.IGNORECASE)
            if len(ddm_matches) >= 2:
                lat = ddm_to_dd(*ddm_matches[0])
                lon = ddm_to_dd(*ddm_matches[1])
                coords.append((lon, lat))
                i += 6
                continue

            # Decimal degrees
            lat = float(tokens[i])
            lon = float(tokens[i + 1])
            coords.append((lon, lat))
            i += 2
            continue

        except Exception:
            skipped.append(" ".join(tokens[i:i+4]))
        i += 1

    # Fallback: USGS-style integers
    fallback_coords = []
    ints = re.findall(r'\d{4,5}', text)
    if len(ints) >= 2:
        for j in range(0, len(ints) - 1, 2):
            try:
                lat = int(ints[j]) / 100.0
                lon = -int(ints[j + 1]) / 100.0
                fallback_coords.append((lon, lat))
            except:
                continue
        if fallback_coords:
            coords.extend(fallback_coords)

    return coords, skipped

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
        parsed_coords, skipped_points = parse_coords(raw_input)
        if len(parsed_coords) < 3:
            st.error(f"Only detected {len(parsed_coords)} valid points — need at least 3 to form a polygon.")
        else:
            if parsed_coords[0] != parsed_coords[-1]:
                parsed_coords.append(parsed_coords[0])
            st.session_state["coords"] = parsed_coords
            st.session_state["skipped"] = skipped_points
    else:
        st.warning("Please enter some coordinates.")

# --- Main Output ---
if "coords" in st.session_state:
    coords = st.session_state["coords"]
    skipped = st.session_state.get("skipped", [])

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

    # --- Map + Population Estimate ---
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    lon_center = sum([pt[0] for pt in coords]) / len(coords)
    lat_center = sum([pt[1] for pt in coords]) / len(coords)
    m = folium.Map(location=[lat_center, lon_center], zoom_start=9, tiles="CartoDB positron")
    folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color="blue", fill=True).add_to(m)

    map_anchor = st.empty()
    with map_anchor.container():
        st_folium(m, width=700, height=400)

        raster_path = "data/landscan-global-2023.tif"
        population = estimate_population_from_coords(coords, raster_path)
        if population is not None:
            st.success(f"Estimated Population: {population:,.0f}")
            st.caption("Note: LandScan represents ambient population (24-hour average).")

    # --- Skipped Points ---
    if skipped:
        filtered_skipped = [s for s in skipped if not re.match(r'LAT|LON|HEADER|ID', s, re.IGNORECASE)]
        if filtered_skipped:
            st.warning(f"Skipped {len(filtered_skipped)} unrecognized coordinate group(s):")
            for point in filtered_skipped:
                st.text(f"• {point}")

# --- Attribution ---
st.markdown("---")
st.markdown(
    "<p style='font-size: 0.8rem; text-align: center; color: grey;'>Population data © Oak Ridge National Laboratory. "
    "Distributed under <a href='https://creativecommons.org/licenses/by/4.0/' target='_blank'>CC BY 4.0</a>.</p>",
    unsafe_allow_html=True
)
