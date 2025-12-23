import streamlit as st
import pandas as pd
import folium
import numpy as np
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("DTDC Network Connections Explorer")

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    result = pd.read_csv("result.csv")
    nodes = pd.read_csv("nodes.csv")
    return result, nodes

result, nodes = load_data()

# =========================
# SIDEBAR – CONNECTION PATH
# =========================
st.sidebar.header("🔗 Connection Path")

paths = sorted(result["connection_full"].dropna().unique())
selected_path = st.sidebar.selectbox("Select connection path", paths)

path_df = result[result["connection_full"] == selected_path].copy()

# =========================
# ORIGIN FILTER (NEW)
# =========================
st.sidebar.header("🏭 Origin Filter")

origins = sorted(path_df["LEG_ORIGIN_CODE"].unique())
selected_origins = st.sidebar.multiselect(
    "Select Origin Codes",
    origins,
    default=origins
)

path_df = path_df[path_df["LEG_ORIGIN_CODE"].isin(selected_origins)]

# =========================
# TIME FILTER
# =========================
st.sidebar.header("⏱ Time Filter")

unique_times = sorted(path_df["Connection Departure Time"].dropna().unique())

if len(unique_times) < 2:
    start_time = end_time = unique_times[0]
else:
    start_time, end_time = st.sidebar.select_slider(
        "Departure Time Window",
        options=unique_times,
        value=(unique_times[0], unique_times[-1])
    )

path_df = path_df[
    (path_df["Connection Departure Time"] >= start_time) &
    (path_df["Connection Departure Time"] <= end_time)
]

# =========================
# SLA + MODE FILTER
# =========================
st.sidebar.header("🎨 Filters")

sla_filter = st.sidebar.multiselect(
    "SLA",
    ["GREEN", "ORANGE", "RED"],
    default=["GREEN", "ORANGE", "RED"]
)

mode_filter = st.sidebar.multiselect(
    "Mode",
    path_df["Mode"].unique().tolist(),
    default=path_df["Mode"].unique().tolist()
)

path_df = path_df[
    path_df["SLA_COLOR"].isin(sla_filter) &
    path_df["Mode"].isin(mode_filter)
]

# =========================
# METRICS
# =========================
total = len(path_df)
red = (path_df["SLA_COLOR"] == "RED").sum()
orange = (path_df["SLA_COLOR"] == "ORANGE").sum()
green = (path_df["SLA_COLOR"] == "GREEN").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Connections", total)
c2.metric("🟢 Green %", f"{green/total*100:.1f}%" if total else "0%")
c3.metric("🟠 Orange %", f"{orange/total*100:.1f}%" if total else "0%")
c4.metric("🔴 Red %", f"{red/total*100:.1f}%" if total else "0%")

# =========================
# JOIN COORDINATES
# =========================
path_df = path_df.merge(
    nodes, left_on="LEG_ORIGIN_CODE", right_on="CODE"
).rename(columns={"lat": "o_lat", "lon": "o_lon"}).drop(columns="CODE")

path_df = path_df.merge(
    nodes, left_on="LEG_DEST_CODE", right_on="CODE"
).rename(columns={"lat": "d_lat", "lon": "d_lon"}).drop(columns="CODE")

# =========================
# DUPLICATE EDGE INDEX
# =========================
path_df["dup_index"] = (
    path_df.groupby(["LEG_ORIGIN_CODE", "LEG_DEST_CODE"]).cumcount()
)

# =========================
# CURVE FUNCTION
# =========================
def curved_line(lat1, lon1, lat2, lon2, offset=0.12, n=30):
    lats = np.linspace(lat1, lat2, n)
    lons = np.linspace(lon1, lon2, n)

    dx, dy = lon2 - lon1, lat2 - lat1
    length = np.sqrt(dx**2 + dy**2) + 1e-6

    px, py = -dy / length, dx / length
    curve = np.sin(np.linspace(0, np.pi, n))

    lats += py * offset * curve
    lons += px * offset * curve

    return list(zip(lats, lons))

# =========================
# MAP INIT (AUTO ZOOM)
# =========================
center_lat = np.mean(pd.concat([path_df.o_lat, path_df.d_lat]))
center_lon = np.mean(pd.concat([path_df.o_lon, path_df.d_lon]))

m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

# =========================
# LAYERS BY SLA
# =========================
sla_layers = {
    "GREEN": folium.FeatureGroup(name="🟢 Green"),
    "ORANGE": folium.FeatureGroup(name="🟠 Orange"),
    "RED": folium.FeatureGroup(name="🔴 Red")
}

color_map = {"GREEN": "green", "ORANGE": "orange", "RED": "red"}

# =========================
# DRAW CONNECTIONS
# =========================
for _, row in path_df.iterrows():
    coords = curved_line(
        row.o_lat, row.o_lon,
        row.d_lat, row.d_lon,
        offset=0.1 * (row.dup_index + 1)
    )

    folium.PolyLine(
        coords,
        color=color_map[row.SLA_COLOR],
        weight=3,
        opacity=0.75,
        popup=f"""
        <b>{row.LEG_ORIGIN_CODE} → {row.LEG_DEST_CODE}</b><br>
        Mode: {row.Mode}<br>
        Departure: {row['Connection Departure Time']}<br>
        Buffer: {row.time_diff_min} min<br>
        SLA: {row.SLA_COLOR}
        """
    ).add_to(sla_layers[row.SLA_COLOR])

# =========================
# NODE CLUSTERING (DECLUTTER)
# =========================
node_cluster = MarkerCluster(name="Nodes")

used_nodes = pd.concat([
    path_df[["LEG_ORIGIN_CODE", "o_lat", "o_lon"]]
        .rename(columns={"LEG_ORIGIN_CODE": "code", "o_lat": "lat", "o_lon": "lon"}),
    path_df[["LEG_DEST_CODE", "d_lat", "d_lon"]]
        .rename(columns={"LEG_DEST_CODE": "code", "d_lat": "lat", "d_lon": "lon"})
]).drop_duplicates()

for _, n in used_nodes.iterrows():
    folium.CircleMarker(
        location=[n.lat, n.lon],
        radius=5,
        color="black",
        fill=True,
        fill_opacity=0.9,
        popup=f"<b>{n.code}</b>"
    ).add_to(node_cluster)

# =========================
# ADD EVERYTHING
# =========================
for layer in sla_layers.values():
    layer.add_to(m)

node_cluster.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# =========================
# RENDER
# =========================
st_folium(m, width=1300, height=650)
