import streamlit as st
import simplekml
import re

st.title("LAT...LON to KML Converter")

raw_input = st.text_area("Paste LAT...LON formatted coordinates below:")

def parse_coords(text):
    nums = re.findall(r'\d{4}', text)
    coords = []
    for i in range(0, len(nums), 2):
        lat = int(nums[i]) / 100.0
        lon = -int(nums[i+1]) / 100.0  # western hemisphere
        coords.append((lat, lon))
    if coords[0] != coords[-1]:
        coords.append(coords[0])  # close the polygon
    return coords

if st.button("Generate KML"):
    if raw_input:
        coords = parse_coords(raw_input)
        kml = simplekml.Kml()
        kml.newpolygon(name="My Polygon", outerboundaryis=coords)
        kml_bytes = kml.kml().encode('utf-8')
        st.download_button("Download KML", kml_bytes, file_name="polygon.kml", mime="application/vnd.google-earth.kml+xml")
    else:
        st.warning("Please paste some coordinates.")
