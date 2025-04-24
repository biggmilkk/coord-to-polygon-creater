import streamlit as st
import simplekml
import folium
import re
from streamlit_folium import st_folium

st.set_page_config(page_title="KML Polygon Generator", layout="centered")

# --- Title ---
st.markdown("<h2 style='text-align: center;'>Coordinates → KML Polygon Generator</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Paste your coordinates below to visualize and export a KML polygon.</p>",
    unsafe_allow_html=True
)

# --- Input ---
raw_input = st.text_area(
    "📍 Coordinates:",
    placeholder="Example: LAT...LON 3906 10399 3924 10393 3921 10357 3902 10361",
    height=150,
    key="coord_input"
)

# --- Parse function ---
def parse_coords(text):
    tokens = re.findall(r'\d+', text)
    coords = []
    i = 0
    while i < len(tokens) - 1:
        try:
            lat = int(tokens[i]) / 100.0
            lon = -int(tokens[i + 1]) / 100.0
            coords.append((lon, lat))
        except ValueError:
            pass
        i += 2
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

# --- Button to trigger generation ---
if st.button("Generate KML and Map"):
    if raw_input.strip():
        parsed_coords = parse_coords(raw_input)
        if len(parsed_coords) < 4:
            st.error("🚫 Not enough points to form a polygon.")
        else:
            st.session_state["coords"] = parsed_coords
    else:
        st.warning("Please enter some coordinates.")

# --- Show KML and map if available ---
if "coords" in st.session_state:
    coords = st.session_state["coords"]

    # --- KML Generation ---
    kml = simplekml.Kml()
    kml.newpolygon(name="My Polygon", outerboundaryis=coords)
    kml_bytes = kml.kml().encode("utf-8")

    st.success("✅ KML polygon created!")
    st.download_button(
        label="📥 Download KML File",
        data=kml_bytes,
        file_name="polygon.kml",
        mime="application/vnd.google-earth.kml+xml",
        use_container_width=True
    )

    # --- Map Preview ---
    st.markdown("### 🗺️ Polygon Preview Map")
    lon_center = sum([pt[0] for pt in coords]) / len(coords)
    lat_center = sum([pt[1] for pt in coords]) / len(coords)
    m = folium.Map(location=[lat_center, lon_center], zoom_start=9, tiles="CartoDB positron")
    folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color="blue", fill=True).add_to(m)
    st_folium(m, width=700, height=500)
