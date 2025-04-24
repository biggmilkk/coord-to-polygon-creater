import streamlit as st
import simplekml
import re

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

# --- Title Section ---
st.markdown("<h2 style='text-align: center;'>LAT...LON → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Convert LAT...LON coordinates to a valid KML polygon file for Google Earth or Mapbox.</p>",
    unsafe_allow_html=True
)

# --- Coordinate Input ---
raw_input = st.text_area(
    "📍 Paste your LAT...LON coordinates below",
    placeholder="Example: 3906 10399 3924 10393 3921 10357 3902 10361",
    height=150
)

# --- Parser ---
def parse_coords(text):
    tokens = re.findall(r'\d+', text)
    coords = []
    i = 0
    while i < len(tokens) - 1:
        try:
            lat = int(tokens[i]) / 100.0
            lon = -int(tokens[i+1]) / 100.0  # west = negative
            coords.append((lon, lat))
        except ValueError:
            continue
        i += 2
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

# --- Generate KML ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("Generate KML", use_container_width=True):
        if raw_input.strip() == "":
            st.warning("Please enter coordinates above.")
        else:
            try:
                coords = parse_coords(raw_input)
                if len(coords) < 4:
                    st.error("You need at least 3 points to form a polygon.")
                else:
                    kml = simplekml.Kml()
                    kml.newpolygon(name="Polygon", outerboundaryis=coords)
                    kml_bytes = kml.kml().encode("utf-8")
                    st.success("✅ KML created!")
                    st.download_button(
                        label="📥 Download KML File",
                        data=kml_bytes,
                        file_name="polygon.kml",
                        mime="application/vnd.google-earth.kml+xml",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"An error occurred: {e}")
