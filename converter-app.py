import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="LAT...LON Polygon Viewer", layout="centered")
st.title("LAT...LON Polygon Viewer")

# --- DM to DD conversion ---
def dm_to_dd(dm):
    degrees = int(dm) // 100
    minutes = int(dm) % 100
    return degrees + minutes / 60

# --- Input block ---
def parse_latlon_block():
    # Manual block input by rows
    rows = [
        [4019, 8042, 4035, 8035, 4035, 8027, 4043, 8013],
        [4036, 7994, 4020, 8003, 4010, 8009, 4004, 8018],
        [4003, 8028, 3999, 8039, 4003, 8051, 4004, 8051],
        [4007, 8038, 4012, 8034, 4019, 8036]
    ]

    coords = []
    for row in rows:
        for i in range(0, len(row), 2):
            lat = dm_to_dd(row[i])
            lon = -dm_to_dd(row[i + 1])  # West longitude
            coords.append((lon, lat))
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

coords = parse_latlon_block()

# --- Show parsed coordinates ---
st.write("### Parsed Coordinates (Longitude, Latitude):")
st.write(coords)

# --- Show on map ---
st.write("### Map Preview")
m = folium.Map(location=[40.4, -80.3], zoom_start=8)
folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color='blue', fill=True).add_to(m)
st_folium(m, width=700, height=500)

# --- Download GeoJSON ---
import json
geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]  # Already (lon, lat)
            },
            "properties": {}
        }
    ]
}
st.download_button("Download GeoJSON", json.dumps(geojson).encode("utf-8"), "polygon.geojson", "application/geo+json")
