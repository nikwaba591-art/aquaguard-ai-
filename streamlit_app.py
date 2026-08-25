import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="AquaGuard AI — Rwanda", layout="wide", page_icon="💧")

# ---------------- Load data ----------------
@st.cache_data
def load_data():
    return pd.read_csv("water_points_scored.csv")

try:
    df = load_data()
except FileNotFoundError:
    st.error("water_points_scored.csv not found. Upload it to the same folder as this app.")
    st.stop()

# Force numeric columns that sometimes load as text
if "risk_pct" in df.columns:
    df["risk_pct"] = pd.to_numeric(df["risk_pct"], errors="coerce")
    df = df.dropna(subset=["risk_pct"])
if "#lat_deg" in df.columns:
    df["#lat_deg"] = pd.to_numeric(df["#lat_deg"], errors="coerce")
if "#lon_deg" in df.columns:
    df["#lon_deg"] = pd.to_numeric(df["#lon_deg"], errors="coerce")

def risk_band(pct):
    if pct >= 70:
        return "High"
    elif pct >= 40:
        return "Medium"
    return "Low"

df["risk_band"] = df["risk_pct"].apply(risk_band)

BAND_COLOR = {"High": "#C1543A", "Medium": "#E8993A", "Low": "#3F8F6F"}
BAND_COLOR_RGB = {"High": [193, 84, 58], "Medium": [232, 153, 58], "Low": [63, 143, 111]}

# ---------------- Header ----------------
st.title("💧 AquaGuard AI")
st.caption("AI-powered failure prediction for rural water points in Rwanda")

# ---------------- Sidebar filters ----------------
st.sidebar.header("Filters")

if "#adm2" in df.columns:
    districts = ["All"] + sorted(df["#adm2"].dropna().unique().tolist())
else:
    districts = ["All"]
district_choice = st.sidebar.selectbox("District", districts, index=0)

band_choice = st.sidebar.multiselect(
    "Risk level", options=["High", "Medium", "Low"], default=["High", "Medium", "Low"]
)

min_risk = st.sidebar.slider("Minimum risk score (%)", 0, 100, 0)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Legend**\n\n"
    "🔴 High risk (≥70%) — inspect first\n\n"
    "🟠 Medium risk (40–69%)\n\n"
    "🟢 Low risk (<40%)"
)

filtered = df.copy()
if district_choice != "All" and "#adm2" in df.columns:
    filtered = filtered[filtered["#adm2"] == district_choice]
filtered = filtered[filtered["risk_pct"] >= min_risk]
filtered = filtered[filtered["risk_band"].isin(band_choice)]

# ---------------- KPIs ----------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Water points shown", f"{len(filtered):,}")
col2.metric("Avg. risk score", f"{filtered['risk_pct'].mean():.1f}%" if len(filtered) else "—")
col3.metric("🔴 High risk", int((filtered["risk_band"] == "High").sum()))
col4.metric("🟢 Low risk", int((filtered["risk_band"] == "Low").sum()))

st.markdown("---")

tab_map, tab_list, tab_districts, tab_alerts = st.tabs(
    ["🗺️ Risk map", "📋 At-risk list", "📊 By district", "📲 Alerts"]
)

# ---------------- TAB: Map ----------------
with tab_map:
    if "#lat_deg" in filtered.columns and "#lon_deg" in filtered.columns:
        map_df = filtered.dropna(subset=["#lat_deg", "#lon_deg"]).rename(
            columns={"#lat_deg": "lat", "#lon_deg": "lon"}
        )
        if len(map_df):
            map_df["r"] = map_df["risk_band"].map(lambda b: BAND_COLOR_RGB[b][0])
            map_df["g"] = map_df["risk_band"].map(lambda b: BAND_COLOR_RGB[b][1])
            map_df["b"] = map_df["risk_band"].map(lambda b: BAND_COLOR_RGB[b][2])

            view = pdk.ViewState(
                latitude=float(map_df["lat"].mean()),
                longitude=float(map_df["lon"].mean()),
                zoom=7.3,
                pitch=0,
            )
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_df,
                get_position="[lon, lat]",
                get_fill_color="[r, g, b, 190]",
                get_radius=450,
                radius_min_pixels=3,
                radius_max_pixels=14,
                pickable=True,
                stroked=True,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=0.5,
            )
            deck = pdk.Deck(
                map_style=None,  # uses free default basemap - no Mapbox token needed
                initial_view_state=view,
                layers=[layer],
                tooltip={"text": "Risk: {risk_pct}%\nDistrict: {#adm2}"},
            )
            st.pydeck_chart(deck, use_container_width=True, height=560)
            st.caption("🔴 High risk · 🟠 Medium risk · 🟢 Low risk — zoom/drag to explore")
        else:
            st.info("No water points with valid coordinates match your current filters.")
    else:
        st.warning("Latitude/longitude columns not found in this dataset — map unavailable.")

# ---------------- TAB: At-risk list ----------------
with tab_list:
    st.subheader("Top 15 at-risk water points")
    st.caption("Ranked highest risk first — recommend inspecting these first.")

    name_col = "#water_point_name" if "#water_point_name" in filtered.columns else None
    top = filtered.sort_values("risk_pct", ascending=False).head(15)

    for _, row in top.iterrows():
        band = row["risk_band"]
        color = BAND_COLOR[band]
        name = row.get(name_col, "Unnamed water point") if name_col else "Unnamed water point"
        district = row.get("#adm2", "Unknown district")
        c1, c2, c3 = st.columns([5, 3, 2])
        with c1:
            st.markdown(f"**{name}**")
            st.caption(f"📍 {district}")
        with c2:
            st.markdown(
                f"<span style='background-color:{color}22;color:{color};"
                f"padding:3px 10px;border-radius:12px;font-weight:600;font-size:13px'>"
                f"{band} risk</span>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(f"**{row['risk_pct']:.1f}%**")
        st.divider()

# ---------------- TAB: By district ----------------
with tab_districts:
    if "#adm2" in filtered.columns and len(filtered):
        st.subheader("Average risk by district")
        district_avg = (
            filtered.groupby("#adm2")["risk_pct"]
            .mean()
            .sort_values(ascending=False)
            .head(15)
            .reset_index()
            .rename(columns={"#adm2": "District", "risk_pct": "Avg risk %"})
        )
        st.bar_chart(district_avg.set_index("District"), color="#C1543A")

        st.subheader("Water points counted per district")
        district_count = (
            filtered.groupby("#adm2").size().sort_values(ascending=False).head(15)
        )
        st.bar_chart(district_count, color="#0E4C4C")
    else:
        st.info("District column not available in this dataset.")

# ---------------- TAB: Alerts ----------------
with tab_alerts:
    st.subheader("📲 Maintenance alert simulation")
    st.caption(
        "Demo only — in production this connects to Africa's Talking or Twilio "
        "to send real SMS to district technicians."
    )

    top10 = filtered.sort_values("risk_pct", ascending=False).head(10)

    if st.button("🚨 Send alerts for top 10 at-risk points", type="primary"):
        progress = st.progress(0, text="Preparing alerts...")
        log_rows = []
        for i, (_, row) in enumerate(top10.iterrows()):
            name = row.get("#water_point_name", "Water point") if "#water_point_name" in top10.columns else "Water point"
            district = row.get("#adm2", "Unknown")
            msg = f"'{name}' ({district}) flagged at {row['risk_pct']:.1f}% failure risk — inspect within 7 days."
            log_rows.append({"water_point": name, "district": district, "risk_pct": row["risk_pct"], "message": msg})
            progress.progress((i + 1) / len(top10), text=f"Sending alert {i+1}/{len(top10)}...")
        progress.empty()

        st.success(f"✅ {len(top10)} alerts sent to district technicians.")
        log_df = pd.DataFrame(log_rows)
        st.dataframe(log_df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Download alert log (CSV)",
            log_df.to_csv(index=False),
            file_name="aquaguard_alert_log.csv",
            mime="text/csv",
        )

st.markdown("---")
with st.expander("ℹ️ About this model"):
    st.write(
        "AquaGuard AI scores each registered water point using a Random Forest "
        "classifier trained on pump age, water source type, management model, "
        "and district — predicting the likelihood a point is non-functional. "
        "Built with scikit-learn, deployed with Streamlit."
    )
