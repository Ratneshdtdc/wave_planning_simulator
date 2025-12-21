import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("DTDC's Network Connections Explorer")

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
selected_path = st.sidebar.selectbox(
    "Select connection path",
    paths
)

# Filter by selected path
path_df = result[result["connection_full"] == selected_path].copy()

# =========================
# TIME SLIDER (MINUTES)
# =========================
st.sidebar.header("⏱ Time Filter")

min_t = path_df["Connection Departure Time"].min()
max_t = path_df["Connection Departure Time"].max()

start_time, end_time = st.sidebar.select_slider(
    "Departure Time Window",
    options=sorted(path_df["Connection Departure Time"].unique()),
    value=(min_t, max_t)
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
    ["RED", "ORANGE", "GREEN"],
    default=["RED", "ORANGE", "GREEN"]
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
# METRICS (OPS GRADE)
# =========================
total = len(path_df)
red = (path_df["SLA_COLOR"] == "RED").sum()
orange = (path_df["SLA_COLOR"] == "ORANGE").sum()
green = (path_df["SLA_COLOR"] == "GREEN").sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Connections", total)
col2.metric("🟢 Green %", f"{(green/total*100):.1f}%" if total else "0%")
col3.metric("🟠 Orange %", f"{(orange/total*100):.1f}%" if total else "0%")
col4.metric("🔴 Red %", f"{(red/total*100):.1f}%" if total else "0%")

# Risk score (simple & interpretable)
risk_score = (red*3 + orange*2 + green*1) / max(total, 1)
st.caption(f"⚠️ Risk Score (lower is better): **{risk_score:.2f}**")

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
# MAP
# =========================
m = folium.Map(location=[22, 78], zoom_start=5)

color_map = {
    "GREEN": "green",
    "ORANGE": "orange",
    "RED": "red"
}

for _, row in path_df.iterrows():
    folium.PolyLine(
        [(row.o_lat, row.o_lon), (row.d_lat, row.d_lon)],
        color=color_map[row.SLA_COLOR],
        weight=4,
        opacity=0.85,
        tooltip=f"""
        {row.LEG_ORIGIN_CODE} → {row.LEG_DEST_CODE}<br>
        Departure: {row['Connection Departure Time']}<br>
        Buffer: {row.time_diff_min} min<br>
        SLA: {row.SLA_COLOR}
        """
    ).add_to(m)

st_folium(m, width=1300, height=650)
