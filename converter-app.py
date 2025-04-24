import streamlit as st
import simplekml
import folium
from streamlit_folium import st_folium
import re

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

st.title("Coordinates → KML Polygon Generator")
st.markdown("Paste coordinates below to generate a polygon, preview on map, and download as KML.")

raw_input = st.text_area("Coordinates:", placeholder="34.2482, -98.6066\n34.25 -98.40\n3424 9860", height=180)

def parse_coords(text):
    coords = []
    text = text.replace(",", " ")
    tokens = re.findall(r"-?\d+\.?\d*", text)
    i = 0
    while i < len(tokens) - 1:
        try:
            lat = float(tokens[i])
            lon = float(tokens[i + 1])
            if abs(lat) > 90:
                lat = lat / 100.0
            if abs(lon) > 180:
                lon = -abs(lon / 100.0)
            coords.append((lon, lat))
        except:
            pass
        i += 2
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

if st.button("Generate Map"):
    if raw_input.strip():
        coords = parse_coords(raw_input)
        if len(coords) >= 3:
            st.success("Polygon generated.")

            # Download KML
            kml = simplekml.Kml()
            kml.newpolygon(name="My Polygon", outerboundaryis=coords)
            kml_bytes = kml.kml().encode("utf-8")
            st.download_button("Download KML", kml_bytes, "polygon.kml", mime="application/vnd.google-earth.kml+xml")

            # Map
            lon_center = sum(pt[0] for pt in coords) / len(coords)
            lat_center = sum(pt[1] for pt in coords) / len(coords)
            m = folium.Map(location=[lat_center, lon_center], zoom_start=8)
            folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color="blue", fill=True).add_to(m)
            st_folium(m, width=700, height=400)
        else:
            st.error("Need at least 3 valid coordinate pairs.")
