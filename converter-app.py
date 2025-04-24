import streamlit as st
import simplekml
import re

st.set_page_config(page_title="LAT...LON to KML Converter")
st.title("🗺️ LAT...LON to Polygon KML Converter")

st.markdown("""
Paste coordinates in the `LAT...LON` format (e.g. `3906 10399 3924 10393 ...`) below.
This app will convert them into a polygon and let you download a KML file for use in Google Earth, Mapbox, etc.

🔁 Format: Each coordinate pair is in hundredths of degrees (e.g. `3906 10399` → 39.06°N, -103.99°W)
""")

# Text input
raw_input = st.text_area("Enter LAT...LON formatted coordinates:", height=200)

def parse_coords(text):
    tokens = re.findall(r'\d+', text)
    coords = []
    i = 0
    while i < len(tokens) - 1:
        lat_raw = tokens[i]
        lon_raw = tokens[i+1]

        try:
            # Latitude: always 4 digits
            lat = int(lat_raw) / 100.0

            # Longitude: assume 4 or 5 digits, always negative (western hemisphere)
            lon = -int(lon_raw) / 100.0

            coords.append((lon, lat))  # KML wants (lon, lat)
        except ValueError:
            continue  # skip bad pairs

        i += 2

    # Close polygon if not already closed
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    return coords

# Button to trigger KML generation
if st.button("Generate KML"):
    if raw_input:
        try:
            coords = parse_coords(raw_input)
            if len(coords) < 4:
                st.error("You need at least 3 points (plus 1 to close the polygon) to form a valid shape.")
            else:
                kml = simplekml.Kml()
                kml.newpolygon(name="My Polygon", outerboundaryis=coords)
                kml_bytes = kml.kml().encode('utf-8')
                st.success("✅ KML file created! Download below.")
                st.download_button("Download KML", kml_bytes, file_name="polygon.kml", mime="application/vnd.google-earth.kml+xml")
        except Exception as e:
            st.error(f"⚠️ Error creating KML: {e}")
    else:
        st.warning("Please enter some coordinates above.")
