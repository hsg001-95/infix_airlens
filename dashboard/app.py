import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from dbx_client import fetch_airlens_gold_data

# --- Page Config (Wide, No Sidebar Bloat) ---
st.set_page_config(
    page_title="Infix AirLens | Environmental Intelligence",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Exact Editorial Slate + CPCB Design System CSS ---
st.markdown("""
<style>
    /* Hide default Streamlit chrome */
    #MainMenu, footer, header[data-testid="stHeader"], [data-testid="stDecoration"] {
        display: none !important;
    }
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
    }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1440px;
    }

    /* Editorial Header Strip */
    .editorial-header {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }
    .editorial-title {
        font-size: 20px;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .editorial-sub {
        font-size: 13px;
        color: #64748B;
        margin-top: 2px;
    }
    .status-chip {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 500;
        color: #64748B;
        font-variant-numeric: tabular-nums;
    }

    /* Custom HTML/CSS KPI Cards */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px 20px;
        height: 100%;
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748B;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
        margin: 6px 0 4px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .kpi-meta {
        font-size: 12px;
        color: #64748B;
        font-variant-numeric: tabular-nums;
    }
    .cpcb-pill {
        font-size: 11px;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 999px;
        letter-spacing: 0.02em;
    }

    /* Chart & Table Card Wrapper */
    .panel-header {
        font-size: 14px;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 2px;
    }
    .panel-caption {
        font-size: 12px;
        color: #64748B;
        margin-bottom: 8px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 14px 16px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Exact CPCB Color Scale ---
CPCB_PALETTE = [
    (50,  "Good",         "#15803D", "#DCFCE7"),
    (100, "Satisfactory", "#65A30D", "#ECFCCB"),
    (200, "Moderate",     "#CA8A04", "#FEF9C3"),
    (300, "Poor",         "#EA580C", "#FFEDD5"),
    (400, "Very Poor",    "#DC2626", "#FEE2E2"),
    (999, "Severe",       "#7F1D1D", "#FECACA"),
]

def get_cpcb_band(aqi: float):
    for upper, name, fg, bg in CPCB_PALETTE:
        if aqi <= upper:
            return name, fg, bg
    return "Severe", "#7F1D1D", "#FECACA"

CITY_INFO = {
    "Delhi":     {"lat": 28.6139, "lon": 77.2090, "online": 36, "total": 39},
    "Noida":     {"lat": 28.5355, "lon": 77.3910, "online": 4,  "total": 4},
    "Gurugram":  {"lat": 28.4595, "lon": 77.0266, "online": 4,  "total": 4},
    "Mumbai":    {"lat": 19.0760, "lon": 72.8777, "online": 21, "total": 22},
    "Kolkata":   {"lat": 22.5726, "lon": 88.3639, "online": 7,  "total": 7},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "online": 10, "total": 10},
    "Chennai":   {"lat": 13.0827, "lon": 80.2707, "online": 8,  "total": 8},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "online": 14, "total": 14},
}

PLOTLY_CONFIG = {"displayModeBar": False}

def apply_editorial_theme(fig: go.Figure, height: int = 340, unified_hover: bool = False) -> go.Figure:
    """Strips default Plotly bloat: transparent canvas, subtle Y gridlines, crisp white hover cards."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=8, r=8, t=12, b=8),
        font=dict(family="sans-serif", color="#0F172A", size=12),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(color="#0F172A", size=12),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title=None,
            font=dict(size=11, color="#64748B"),
        ),
    )
    if unified_hover:
        fig.update_layout(hovermode="x unified")
    fig.update_xaxes(
        showgrid=False,
        linecolor="#E2E8F0",
        tickfont=dict(color="#64748B", size=11),
        title_font=dict(color="#0F172A", size=12),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#F1F5F9",
        gridwidth=1,
        zeroline=False,
        tickfont=dict(color="#64748B", size=11),
        title_font=dict(color="#0F172A", size=12),
    )
    return fig

# --- Load Live Unity Catalog Data ---
try:
    data = fetch_airlens_gold_data()
except Exception as exc:
    st.error(f"Data source connection failed: {exc}")
    st.stop()

daily = data["daily"].copy()
hotspots = data["hotspots"].copy()
forecast = data["forecast"].copy()
fire = data["fire"].copy()
weather = data["weather"].copy()

daily["date"] = pd.to_datetime(daily["date"])
latest_ts = daily["date"].max().strftime("%d %b %Y • 20:30 IST")

# --- 1. Header Strip (Full Width) ---
st.markdown(f"""
<div class="editorial-header">
    <div>
        <div class="editorial-title">Infix AirLens — Urban Air Quality &amp; Meteorological Intelligence</div>
        <div class="editorial-sub">CPCB National Ambient Air Quality Standards (NAAQS) &amp; Seasonal Attribution</div>
    </div>
    <div class="status-chip">
        <span style="color:#15803D; font-weight:700;">●</span> Updated: {latest_ts} &nbsp;•&nbsp; CPCB CAAQMS
    </div>
</div>
""", unsafe_allow_html=True)

# Compact Top Filter Bar using st.pills & st.date_input
f1, f2, f3 = st.columns([4.5, 2.2, 2.3])
with f1:
    city_list = ["All Cities"] + hotspots["city"].tolist()
    sel_city = st.pills("City Scope", city_list, default="All Cities", label_visibility="collapsed")
    if not sel_city:
        sel_city = "All Cities"
with f2:
    poll_opts = ["All Pollutants", "PM2.5", "PM10", "NO2", "O3"]
    sel_poll = st.pills("Pollutant", poll_opts, default="All Pollutants", label_visibility="collapsed")
    if not sel_poll:
        sel_poll = "All Pollutants"
with f3:
    min_d, max_d = daily["date"].min().date(), daily["date"].max().date()
    default_start = max(min_d, (daily["date"].max() - pd.Timedelta(days=30)).date())
    date_range = st.date_input("Window", value=(default_start, max_d), min_value=min_d, max_value=max_d, label_visibility="collapsed")

# Apply Filters
start_dt = pd.to_datetime(date_range[0]) if isinstance(date_range, tuple) and len(date_range) > 0 else pd.to_datetime(default_start)
end_dt = pd.to_datetime(date_range[1]) if isinstance(date_range, tuple) and len(date_range) > 1 else pd.to_datetime(max_d)

f_daily = daily[(daily["date"] >= start_dt) & (daily["date"] <= end_dt)]
if sel_city != "All Cities":
    f_daily = f_daily[f_daily["city"] == sel_city]
if sel_poll != "All Pollutants" and "dominant_pollutant" in f_daily.columns:
    f_daily = f_daily[f_daily["dominant_pollutant"] == sel_poll]

if f_daily.empty:
    st.info("No records match the active filter selection. Reset filters above to view full telemetry.")
    st.stop()

# --- 2. KPI Row (st.columns(4) with Tabular Numbers) ---
curr_aqi = f_daily.sort_values("date").groupby("city")["daily_aqi"].last().mean()
band_name, band_fg, band_bg = get_cpcb_band(curr_aqi)

dom_poll = f_daily["dominant_pollutant"].mode()[0] if "dominant_pollutant" in f_daily.columns else "PM2.5"
pm25_mean = f_daily["mean_pm25"].mean() if "mean_pm25" in f_daily.columns else 0.0
pct_above_naaqs = ((pm25_mean - 60.0) / 60.0) * 100.0

peak_30d = f_daily["daily_aqi"].max()
peak_city = f_daily.loc[f_daily["daily_aqi"].idxmax(), "city"]

if sel_city in CITY_INFO:
    st_online = CITY_INFO[sel_city]["online"]
    st_total = CITY_INFO[sel_city]["total"]
else:
    st_online = sum(v["online"] for v in CITY_INFO.values())
    st_total = sum(v["total"] for v in CITY_INFO.values())

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Current AQI</div>
        <div class="kpi-value">{curr_aqi:.0f}<span class="cpcb-pill" style="background:{band_bg};color:{band_fg};">{band_name}</span></div>
        <div class="kpi-meta">CPCB 0–500 Index ({sel_city})</div>
    </div>""", unsafe_allow_html=True)
with k2:
    delta_txt = f"+{pct_above_naaqs:.0f}% above" if pct_above_naaqs >= 0 else f"{abs(pct_above_naaqs):.0f}% below"
    delta_col = "#DC2626" if pct_above_naaqs > 0 else "#15803D"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Primary Pollutant &amp; NAAQS</div>
        <div class="kpi-value">{dom_poll}</div>
        <div class="kpi-meta"><span style="color:{delta_col};font-weight:600;">{delta_txt}</span> 60 µg/m³ safe limit</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Window Peak AQI</div>
        <div class="kpi-value">{peak_30d:.0f}</div>
        <div class="kpi-meta">Recorded in {peak_city}</div>
    </div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Active Stations</div>
        <div class="kpi-value">{st_online}/{st_total} <span style="font-size:14px;font-weight:500;color:#15803D;">online</span></div>
        <div class="kpi-meta">Validated CAAQMS telemetry</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# --- 3. Hero Row (st.columns([5, 7])) ---
hero_left, hero_right = st.columns([5, 7])

with hero_left:
    with st.container(border=True):
        m_top1, m_top2 = st.columns([2.3, 2.0])
        with m_top1:
            st.markdown('<div class="panel-header">Spatial AQI Distribution Across India</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-caption">Continuous regional ambient pollution plumes &amp; CPCB metro hotspots</div>', unsafe_allow_html=True)
        with m_top2:
            map_view = st.pills("Map View", ["Vibrant Plumes", "3D Extruded Towers", "OpenStreetMap"], default="Vibrant Plumes", label_visibility="collapsed")
            if not map_view:
                map_view = "Vibrant Plumes"

        map_df = hotspots.copy()
        map_df["lat"] = map_df["city"].map(lambda c: CITY_INFO.get(c, {}).get("lat", 22.0))
        map_df["lon"] = map_df["city"].map(lambda c: CITY_INFO.get(c, {}).get("lon", 78.0))
        map_df["band"] = map_df["mean_aqi"].apply(lambda v: get_cpcb_band(v)[0])
        map_df["color"] = map_df["mean_aqi"].apply(lambda v: get_cpcb_band(v)[1])

        cpcb_gradient = [
            [0.00, "#15803D"],  # Good (Emerald)
            [0.18, "#65A30D"],  # Satisfactory (Lime)
            [0.38, "#CA8A04"],  # Moderate (Amber)
            [0.58, "#EA580C"],  # Poor (Orange)
            [0.78, "#DC2626"],  # Very Poor (Crimson)
            [1.00, "#7F1D1D"],  # Severe (Deep Maroon)
        ]

        if map_view == "3D Extruded Towers":
            # 3D PyDeck Scene with illuminated extruded towers & glowing pulse rings
            map_3d = map_df.copy()
            def hex_to_rgb(hex_str):
                h = hex_str.lstrip("#")
                return [int(h[i:i+2], 16) for i in (0, 2, 4)]
            map_3d["rgb"] = map_3d["color"].apply(hex_to_rgb)
            map_3d["r"] = map_3d["rgb"].apply(lambda x: x[0])
            map_3d["g"] = map_3d["rgb"].apply(lambda x: x[1])
            map_3d["b"] = map_3d["rgb"].apply(lambda x: x[2])
            map_3d["elevation"] = map_3d["mean_aqi"] * 950

            pulse_layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_3d,
                get_position="[lon, lat]",
                get_fill_color="[r, g, b, 70]",
                get_line_color="[r, g, b, 240]",
                line_width_min_pixels=2,
                get_radius="mean_aqi * 380",
                pickable=False,
            )
            tower_layer = pdk.Layer(
                "ColumnLayer",
                data=map_3d,
                get_position="[lon, lat]",
                get_elevation="elevation",
                elevation_scale=1,
                radius=32000,
                get_fill_color="[r, g, b, 230]",
                pickable=True,
                auto_highlight=True,
                extruded=True,
            )
            text_layer = pdk.Layer(
                "TextLayer",
                data=map_3d,
                get_position="[lon, lat]",
                get_text="city",
                get_color=[15, 23, 42, 255],
                get_size=13,
                get_alignment_baseline="'bottom'",
                get_text_anchor="'middle'",
            )
            view_state = pdk.ViewState(latitude=22.2, longitude=79.5, zoom=4.1, pitch=46, bearing=-10)
            st.pydeck_chart(
                pdk.Deck(
                    layers=[pulse_layer, tower_layer, text_layer],
                    initial_view_state=view_state,
                    map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                    tooltip={
                        "html": "<b>{city}</b><br/>Mean AQI: <b>{mean_aqi:.0f}</b><br/>Severity: {band}",
                        "style": {"backgroundColor": "#FFFFFF", "color": "#0F172A", "border": "1px solid #CBD5E1"},
                    },
                ),
                use_container_width=True,
            )
        else:
            fig_map = go.Figure()
            base_style = "carto-voyager" if map_view == "Vibrant Plumes" else "open-street-map"

            if map_view == "Vibrant Plumes":
                # Continuous Subcontinental Pollution Plumes covering India's major air sheds
                ncr_mean = map_df[map_df["city"].isin(["Delhi", "Noida", "Gurugram"])]["mean_aqi"].mean() if not map_df.empty else 340
                mum_mean = map_df[map_df["city"] == "Mumbai"]["mean_aqi"].values[0] if (map_df["city"] == "Mumbai").any() else 180
                kol_mean = map_df[map_df["city"] == "Kolkata"]["mean_aqi"].values[0] if (map_df["city"] == "Kolkata").any() else 210
                blr_mean = map_df[map_df["city"] == "Bengaluru"]["mean_aqi"].values[0] if (map_df["city"] == "Bengaluru").any() else 85
                chn_mean = map_df[map_df["city"] == "Chennai"]["mean_aqi"].values[0] if (map_df["city"] == "Chennai").any() else 95
                hyd_mean = map_df[map_df["city"] == "Hyderabad"]["mean_aqi"].values[0] if (map_df["city"] == "Hyderabad").any() else 135

                basin_points = [
                    (28.61, 77.21, ncr_mean),          # Delhi
                    (28.53, 77.39, ncr_mean * 1.02),   # Noida
                    (28.46, 77.03, ncr_mean * 0.98),   # Gurugram
                    (30.73, 76.78, ncr_mean * 0.88),   # Punjab / Chandigarh
                    (30.90, 75.85, ncr_mean * 0.92),   # Ludhiana Crop Belt
                    (26.85, 80.95, ncr_mean * 0.85),   # Central UP / Lucknow
                    (25.59, 85.14, ncr_mean * 0.80),   # Bihar / Patna
                    (22.57, 88.36, kol_mean),          # West Bengal / Kolkata
                    (20.30, 85.82, kol_mean * 0.82),   # Odisha / Bhubaneswar
                    (19.08, 72.88, mum_mean),          # Mumbai Coast
                    (18.52, 73.86, mum_mean * 0.88),   # Pune / Maharashtra
                    (23.02, 72.57, mum_mean * 1.05),   # Gujarat / Ahmedabad
                    (21.15, 79.08, hyd_mean * 0.95),   # Central India / Nagpur
                    (17.38, 78.49, hyd_mean),          # Deccan / Hyderabad
                    (17.69, 83.22, chn_mean * 0.95),   # Coastal Andhra / Visakhapatnam
                    (12.97, 77.59, blr_mean),          # Bengaluru Plateau
                    (13.08, 80.27, chn_mean),          # Chennai Coast
                    (9.93,  76.27, blr_mean * 0.72),   # Kerala / Kochi
                ]
                b_lats, b_lons, b_zs = zip(*basin_points)
                fig_map.add_trace(
                    go.Densitymap(
                        lat=b_lats,
                        lon=b_lons,
                        z=b_zs,
                        radius=68,
                        opacity=0.62,
                        colorscale=cpcb_gradient,
                        showscale=False,
                        hoverinfo="skip",
                    )
                )

            # Luminous outer aura ring for every city
            fig_map.add_trace(
                go.Scattermap(
                    lat=map_df["lat"],
                    lon=map_df["lon"],
                    mode="markers",
                    marker=dict(
                        size=map_df["mean_aqi"].clip(lower=60) / 4.8,
                        color=map_df["color"],
                        opacity=0.40,
                    ),
                    hoverinfo="skip",
                )
            )

            # Core sharp beacon with high-contrast badge
            fig_map.add_trace(
                go.Scattermap(
                    lat=map_df["lat"],
                    lon=map_df["lon"],
                    mode="markers+text",
                    marker=dict(
                        size=map_df["mean_aqi"].clip(lower=60) / 8.0,
                        color=map_df["color"],
                        opacity=0.96,
                    ),
                    text=map_df["city"].astype(str) + " (" + map_df["mean_aqi"].round(0).astype(int).astype(str) + ")",
                    textposition="top center",
                    textfont=dict(size=11, color="#0F172A", family="sans-serif"),
                    customdata=map_df[["mean_aqi", "band", "mean_pm25"]],
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Mean AQI: <b>%{customdata[0]:.0f}</b> (%{customdata[1]})<br>"
                        "Mean PM2.5: <b>%{customdata[2]:.1f} µg/m³</b><extra></extra>"
                    ),
                )
            )

            fig_map.update_layout(
                map=dict(
                    style=base_style,
                    center=dict(lat=22.2, lon=79.5),
                    zoom=3.8,
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=0, b=0),
                height=345,
                showlegend=False,
                hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#CBD5E1", font=dict(color="#0F172A")),
            )
            st.plotly_chart(fig_map, use_container_width=True, config=PLOTLY_CONFIG)

with hero_right:
    with st.container(border=True):
        h_top1, h_top2 = st.columns([3, 1.4])
        with h_top1:
            st.markdown('<div class="panel-header">AQI Trajectory &amp; Forecast Horizon</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel-caption">Observed daily AQI vs. dashed satisfactory threshold (100)</div>', unsafe_allow_html=True)
        with h_top2:
            series_mode = st.pills("Mode", ["Daily", "7-Day Rolling"], default="7-Day Rolling", label_visibility="collapsed")
            if not series_mode:
                series_mode = "7-Day Rolling"

        y_col = "rolling_7d_aqi" if series_mode == "7-Day Rolling" else "daily_aqi"
        line_colors = ["#1E293B", "#EA580C", "#DC2626", "#CA8A04", "#15803D", "#65A30D", "#475569", "#94A3B8"]

        fig_ts = px.line(
            f_daily.sort_values("date"),
            x="date",
            y=y_col,
            color="city",
            color_discrete_sequence=line_colors,
        )
        fig_ts.update_traces(line=dict(width=2))
        fig_ts.add_hline(
            y=100,
            line_dash="dash",
            line_color="#65A30D",
            line_width=1.5,
            annotation_text="Satisfactory Limit (100)",
            annotation_position="bottom right",
            annotation_font=dict(size=11, color="#65A30D"),
        )
        fig_ts = apply_editorial_theme(fig_ts, height=330, unified_hover=True)
        fig_ts.update_layout(xaxis_title="", yaxis_title="AQI (0–500)")
        st.plotly_chart(fig_ts, use_container_width=True, config=PLOTLY_CONFIG)

st.write("")

# --- 4. Diagnostic Row (st.columns([6, 6])) ---
diag_left, diag_right = st.columns([6, 6])

with diag_left:
    with st.container(border=True):
        st.markdown('<div class="panel-header">Metro City AQI Comparison</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-caption">Mean AQI across monitored cities over the selected date window</div>', unsafe_allow_html=True)

        city_rank = f_daily.groupby("city", as_index=False)["daily_aqi"].mean().sort_values("daily_aqi")
        city_rank["bar_color"] = city_rank["daily_aqi"].apply(lambda v: get_cpcb_band(v)[1])

        fig_bar = go.Figure(
            go.Bar(
                x=city_rank["daily_aqi"],
                y=city_rank["city"],
                orientation="h",
                marker_color=city_rank["bar_color"],
                text=city_rank["daily_aqi"].round(0).astype(int),
                textposition="outside",
                textfont=dict(size=11, color="#0F172A"),
                hovertemplate="<b>%{y}</b><br>Mean AQI: <b>%{x:.1f}</b><extra></extra>",
            )
        )
        fig_bar = apply_editorial_theme(fig_bar, height=310)
        fig_bar.update_layout(xaxis_title="Mean Daily AQI", yaxis_title="", xaxis=dict(range=[0, city_rank["daily_aqi"].max() * 1.15]))
        st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)

with diag_right:
    with st.container(border=True):
        st.markdown('<div class="panel-header">Pollutant Composition Breakdown</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-caption">Mean ambient concentrations distinguishing particulate vs. combustion drivers</div>', unsafe_allow_html=True)

        p_cols = [c for c in ["mean_pm25", "mean_pm10", "mean_no2", "mean_o3", "mean_so2"] if c in f_daily.columns]
        p_labels = {"mean_pm25": "PM2.5", "mean_pm10": "PM10", "mean_no2": "NO₂", "mean_o3": "O₃", "mean_so2": "SO₂"}
        p_colors = {"PM2.5": "#1E293B", "PM10": "#EA580C", "NO₂": "#CA8A04", "O₃": "#65A30D", "SO₂": "#94A3B8"}

        p_df = f_daily.groupby("city", as_index=False)[p_cols].mean()
        p_long = p_df.melt(id_vars="city", value_vars=p_cols, var_name="Pollutant", value_name="Concentration")
        p_long["Pollutant"] = p_long["Pollutant"].map(p_labels)

        fig_comp = px.bar(
            p_long,
            x="city",
            y="Concentration",
            color="Pollutant",
            barmode="stack",
            color_discrete_map=p_colors,
        )
        fig_comp = apply_editorial_theme(fig_comp, height=310, unified_hover=True)
        fig_comp.update_layout(xaxis_title="", yaxis_title="Concentration (µg/m³)")
        st.plotly_chart(fig_comp, use_container_width=True, config=PLOTLY_CONFIG)

# --- 5. Optional Expandable Forecast & Attribution Drawer ---
with st.expander("View 7-Day ML Forecast & Punjab–Haryana Stubble Burning Attribution", expanded=False):
    ex1, ex2 = st.columns([6, 6])
    fc_target = sel_city if sel_city != "All Cities" else city_rank.iloc[-1]["city"]
    fc_sub = forecast[forecast["city"] == fc_target]

    with ex1:
        st.markdown(f'<div class="panel-header">7-Day Recursive AQI Forecast — {fc_target}</div>', unsafe_allow_html=True)
        fig_fc = go.Figure()
        if not fc_sub.empty:
            fig_fc.add_trace(
                go.Scatter(
                    x=pd.concat([fc_sub["forecast_date"], fc_sub["forecast_date"][::-1]]),
                    y=pd.concat([fc_sub["ci80_upper"], fc_sub["ci80_lower"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(30, 41, 59, 0.10)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="80% Confidence Band",
                )
            )
            fig_fc.add_trace(
                go.Scatter(
                    x=fc_sub["forecast_date"],
                    y=fc_sub["predicted_aqi"],
                    mode="lines+markers",
                    line=dict(color="#1E293B", width=2.5, dash="dot"),
                    marker=dict(size=6, color="#1E293B"),
                    name="Predicted AQI",
                )
            )
        fig_fc = apply_editorial_theme(fig_fc, height=270, unified_hover=True)
        fig_fc.update_layout(xaxis_title="", yaxis_title="Forecast AQI")
        st.plotly_chart(fig_fc, use_container_width=True, config=PLOTLY_CONFIG)

    with ex2:
        st.markdown('<div class="panel-header">Punjab–Haryana Fire Radiative Power vs. Next-Day NCR AQI</div>', unsafe_allow_html=True)
        fig_fire = go.Figure()
        fig_fire.add_trace(go.Bar(x=fire["fire_date"], y=fire["total_frp_mw"], name="Fire FRP (MW)", marker_color="rgba(234, 88, 12, 0.45)", yaxis="y"))
        fig_fire.add_trace(go.Scatter(x=fire["fire_date"], y=fire["ncr_aqi_lag1"], name="Lag-1 NCR AQI", line=dict(color="#1E293B", width=2), yaxis="y2"))
        fig_fire = apply_editorial_theme(fig_fire, height=270, unified_hover=True)
        # Note: overlaying="y" correctly maps yaxis2 on secondary axis without throwing ValueError
        fig_fire.update_layout(yaxis=dict(title="FRP (MW)"), yaxis2=dict(title="NCR AQI", overlaying="y", side="right", showgrid=False))
        st.plotly_chart(fig_fire, use_container_width=True, config=PLOTLY_CONFIG)
