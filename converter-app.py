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
    "Coordinates:",
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

# --- Show KML and map if available ---
if "coords" in st.session_state:
    coords = st.session_state["coords"]

    # --- KML Generation ---
    kml = simplekml.Kml()
    kml.newpolygon(name="My Polygon", outerboundaryis=coords)
    kml_bytes = kml.kml().encode("utf-8")

    # --- Centered Download Button ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.download_button(
            label="Download KML File",
            data=kml_bytes,
            file_name="polygon.kml",
            mime="application/vnd.google-earth.kml+xml",
            use_container_width=True
        )

    # --- Map Preview ---
    st.markdown("<h4 style='text-align: center;'>Polygon Preview</h4>", unsafe_allow_html=True)
    lon_center = sum([pt[0] for pt in coords]) / len(coords)
    lat_center = sum([pt[1] for pt in coords]) / len(coords)
    m = folium.Map(location=[lat_center, lon_center], zoom_start=9, tiles="CartoDB positron")
    folium.Polygon(locations=[(lat, lon) for lon, lat in coords], color="blue", fill=True).add_to(m)
    st_folium(m, width=700, height=500)

# --- Advanced Analysis: Population from LandScan ---
with st.expander("🔬 Advanced: Estimate Population from LandScan", expanded=False):
    st.markdown("Upload a **GeoJSON polygon** to calculate estimated population using a LandScan raster.")
    
    uploaded_file = st.file_uploader("Upload GeoJSON Polygon", type=["geojson"])
    
    # Replace with the actual path to your LandScan GeoTIFF raster
    landsan_raster = "./landscan_2022.tif"  # Update this path
    
    def calculate_population(polygon_path):
        try:
            stats = zonal_stats(polygon_path, landsan_raster, stats=["sum"])
            return stats[0]["sum"]
        except Exception as e:
            st.error(f"Error: {str(e)}")
            return None

    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        with st.spinner("Calculating population..."):
            population = calculate_population(tmp_path)
            os.unlink(tmp_path)

            if population is not None:
                st.success(f"Estimated Population: {population:,.0f}")
                st.caption("Note: LandScan estimates ambient population (24-hour average).")
