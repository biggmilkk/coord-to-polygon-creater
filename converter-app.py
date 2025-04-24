import streamlit as st
import simplekml
import re

st.set_page_config(page_title="LAT...LON to KML Converter")
st.title("🗺️ LAT...LON to Polygon KML Converter")

st.markdown("""
Paste coordinates in the `LAT...LON` format (e.g. `3389 9745 3387 9745 ...`) below.
This app will convert them into a polygon and let you download a KML file for use in Google Earth, Mapbox, etc.
""")

# Input
raw_input = st.text_area("Enter LAT...LON formatted coordinates:", height=200)

def parse_coords(text):
    nums = re.findall(r'\d{4}', text)
    coords = []
    for i in range(0, len(nums), 2):
        lat = int(nums[i]) / 100.0
        lon = -int(nums[i+1]) / 100.0  # western hemisphere assumed
        coords.append((lon, lat))  # KML expects (lon, lat)
    if coords[0] != coords[-1]:
        coords.append(coords[0])  # close the polygon
    return coords

# Generate KML
if st.button("Generate KML"):
    if raw_input:
        try:
            coords = parse_coords(raw_input)
            kml = simplekml.Kml()
            kml.newpolygon(name="My Polygon", outerboundaryis=coords)
            kml_bytes = kml.kml().encode('utf-8')
            st.success("✅ KML file created! Download below.")
            st.download_button("Download KML", kml_bytes, file_name="polygon.kml", mime="application/vnd.google-earth.kml+xml")
        except Exception as e:
            st.error(f"⚠️ Error creating KML: {e}")
    else:
        st.warning("Please enter some coordinates above.")
