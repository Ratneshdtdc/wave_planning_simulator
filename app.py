import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("🌙 Night Network SLA Visualizer")

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
# SIDEBAR CONTROLS
# =========================
st.sidebar.header("⏱ Time Filter")

start_hour = st.sidebar.slider("Start hour", 0, 23, 18)
end_hour = st.sidebar.slider("End hour", 0, 23, 6)

st.sidebar.header("🎨 SLA Filter")
sla_filter = st.sidebar.multiselect(
    "Show SLA Colors",
    ["RED", "ORANGE", "GREEN"],
    default=["RED", "ORANGE", "GREEN"]
)

mode_filter = st.sidebar.multiselect(
    "Mode",
    result["Mode"].unique().tolist(),
    default=result["Mode"].unique().tolist()
)

# =========================
# TIME WINDOW LOGIC
# =========================
def in_time_window(dep_time, start_h, end_h):
    hour = int(dep_time.split(":")[0])
    if start_h <= end_h:
        return start_h <= hour <= end_h
    else:
        # overnight window
        return hour >= start_h or hour <= end_h

filtered = result[
    result["Connection Departure Time"].apply(
        lambda x: in_time_window(x, start_hour, end_hour)
    )
]

filtered = filtered[
    filtered["SLA_COLOR"].isin(sla_filter) &
    filtered["Mode"].isin(mode_filter)
]

# =========================
# JOIN COORDINATES
# =========================
filtered = filtered.merge(
    nodes, left_on="LEG_ORIGIN_CODE", right_on="CODE"
).rename(columns={"lat": "o_lat", "lon": "o_lon"}).drop(columns="CODE")

filtered = filtered.merge(
    nodes, left_on="LEG_DEST_CODE", right_on="CODE"
).rename(columns={"lat": "d_lat", "lon": "d_lon"}).drop(columns="CODE")

# =========================
# MAP
# =========================
m = folium.Map(location=[22, 78], zoom_start=5)

color_map = {
    "GREEN": "green",
    "ORANGE": "orange",
    "RED": "red"
}

for _, row in filtered.iterrows():
    folium.PolyLine(
        [(row.o_lat, row.o_lon), (row.d_lat, row.d_lon)],
        color=color_map[row.SLA_COLOR],
        weight=3,
        opacity=0.8,
        tooltip=f"""
        {row.LEG_ORIGIN_CODE} → {row.LEG_DEST_CODE}<br>
        Departure: {row['Connection Departure Time']}<br>
        Buffer: {row.time_diff_min} min<br>
        SLA: {row.SLA_COLOR}
        """
    ).add_to(m)

st_folium(m, width=1200, height=650)
