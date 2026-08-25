import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="AquaGuard AI — Rwanda", layout="wide")

st.title("💧 AquaGuard AI")
st.caption("AI-powered failure prediction for rural water points in Rwanda")

@st.cache_data
def load_data():
    return pd.read_csv("water_points_scored.csv")

try:
    df = load_data()
except FileNotFoundError:
    st.error("water_points_scored.csv not found. Upload it to the same folder as this app (from Colab Cell 8/9).")
    st.stop()

# Safety net: force numeric columns that sometimes load as text
if "risk_pct" in df.columns:
    df["risk_pct"] = pd.to_numeric(df["risk_pct"], errors="coerce")
    df = df.dropna(subset=["risk_pct"])

# ---- sidebar filters ----
st.sidebar.header("Filters")
districts = ["All"] + sorted(df["#adm2"].dropna().unique().tolist()) if "#adm2" in df.columns else ["All"]
district_choice = st.sidebar.selectbox("District", districts)

min_risk = st.sidebar.slider("Minimum risk score (%)", 0, 100, 0)

filtered = df.copy()
if district_choice != "All" and "#adm2" in df.columns:
    filtered = filtered[filtered["#adm2"] == district_choice]
filtered = filtered[filtered["risk_pct"] >= min_risk]

# ---- KPIs ----
col1, col2, col3 = st.columns(3)
col1.metric("Water points shown", len(filtered))
col2.metric("Avg. risk score", f"{filtered['risk_pct'].mean():.1f}%" if len(filtered) else "—")
col3.metric("High risk (>70%)", int((filtered['risk_pct'] > 70).sum()))

# ---- map ----
if "#lat_deg" in filtered.columns and "#lon_deg" in filtered.columns:
    filtered["#lat_deg"] = pd.to_numeric(filtered["#lat_deg"], errors="coerce")
    filtered["#lon_deg"] = pd.to_numeric(filtered["#lon_deg"], errors="coerce")
    map_df = filtered.dropna(subset=["#lat_deg", "#lon_deg"]).rename(
        columns={"#lat_deg": "lat", "#lon_deg": "lon"}
    )
    if len(map_df):
        map_df["color_r"] = (map_df["risk_pct"] * 2.55).astype(int)
        map_df["color_g"] = (255 - map_df["risk_pct"] * 2.55).astype(int)

        st.subheader("Risk map")
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(
                latitude=map_df["lat"].mean(), longitude=map_df["lon"].mean(),
                zoom=7, pitch=0),
            layers=[pdk.Layer(
                "ScatterplotLayer", data=map_df,
                get_position='[lon, lat]',
                get_fill_color='[color_r, color_g, 40, 160]',
                get_radius=800, pickable=True)],
            tooltip={"text": "Risk: {risk_pct}%"}
        ))
else:
    st.info("Latitude/longitude columns not found — map skipped, table still works below.")

# ---- top at-risk table ----
st.subheader("Top 10 at-risk water points (recommend inspection first)")
show_cols = [c for c in ["#water_point_name", "#adm2", "risk_pct"] if c in filtered.columns]
top10 = filtered.sort_values("risk_pct", ascending=False).head(10)
st.dataframe(top10[show_cols] if show_cols else top10, use_container_width=True)

# ---- simulated SMS alert ----
st.subheader("📲 Simulated maintenance alert")
if st.button("Send SMS alerts for top 10 at-risk points"):
    for _, row in top10.iterrows():
        name = row.get("#water_point_name", "Water point")
        st.success(f"SMS sent → District officer: '{name}' flagged at {row['risk_pct']}% failure risk. Inspect within 7 days.")

st.caption("Demo dashboard — connect to Africa's Talking / Twilio SMS API for production alert delivery.")
