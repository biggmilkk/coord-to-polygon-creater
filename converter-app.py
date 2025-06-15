import streamlit as st
import simplekml
import folium
import re
import json
from streamlit_folium import st_folium

st.set_page_config(page_title="Polygon Generator", layout="centered")

st.title("🗺️ Polygon Generator from Coordinates")

# --- Parse Degrees + Minutes to Decimal Degrees ---
def dm_to_dd(dm):
    degrees = int(dm) // 100
    minutes = int(dm) % 100
    return degrees + minutes / 60

# --- Coordinate Parser (LAT...LON 4019 8042 ...) ---
def parse_coords(text):
    tokens = re.findall(r'\d+', text)
    coords = []
    for i in range(0, len(tokens) - 1, 2):
        try:
            lat_dm = int(tokens[i])
            lon_dm = int(tokens[i + 1])
            lat = dm_to_dd(lat_dm)
            lon = -dm_to_dd(lon_dm)  # Assume Western Hemisphere
            coords.append((lon, lat))  # Always (lon, lat)
        except:
            continue
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return [coords] if coords else []

# --- Coordinate Input ---
text_input = st.text_area("Paste Coordinates (LAT LON in DM format)", height=200, placeholder="LAT...LON 4019 8042 4035 8035 ...")

# --- Parse Button ---
if st.button("Generate Polygon"):
    polygons = parse_coords(text_input)

    if polygons and polygons[0]:
        st.success("✅ Coordinates parsed and polygon created.")

        # --- Show parsed coords ---
        st.write("Parsed (lon, lat) coordinates:")
        st.write(polygons[0])

        # --- Preview Map (Folium uses lat, lon) ---
        m = folium.Map(tiles="CartoDB positron", zoom_start=6)
        all_points = []
        for poly in polygons:
            latlons = [(lat, lon) for lon, lat in poly]
            folium.Polygon(locations=latlons, color="blue", fill=True).add_to(m)
            all_points.extend(latlons)
        if all_points:
            m.fit_bounds(all_points)
        st_folium(m, width=700, height=400)

        # --- GeoJSON Export ---
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [poly]  # KEEP as (lon, lat)
                    },
                    "properties": {}
                }
                for poly in polygons
            ]
        }
        geojson_bytes = json.dumps(geojson, indent=2).encode("utf-8")
        st.download_button("Download GeoJSON", data=geojson_bytes, file_name="polygon.geojson", mime="application/geo+json")

        # --- KML Export ---
        kml = simplekml.Kml()
        for i, poly in enumerate(polygons):
            kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=poly)
        st.download_button("Download KML", data=kml.kml().encode("utf-8"), file_name="polygon.kml", mime="application/vnd.google-earth.kml+xml")

    else:
        st.warning("⚠️ No valid coordinates parsed.")
