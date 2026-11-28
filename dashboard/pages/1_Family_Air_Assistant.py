import sys
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant.tools.air_tools import (
    get_air_status,
    find_best_windows,
    get_grap_status,
    get_outlook_48h,
    estimate_indoor_pm25,
    estimate_commute_savings,
)
from assistant.agent.loop import run_airlens_assistant

st.set_page_config(page_title="Infix AirLens | Family & Community Air Assistant", page_icon="🌿", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F4F7FB; color: #0F172A; }
    .hero-card {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
        padding: 18px 22px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04); margin-bottom: 14px;
    }
    .impact-box {
        background: #F0FDF4; border: 1px solid #86EFAC; border-radius: 12px; padding: 14px 16px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-card">
    <div style="font-size:22px; font-weight:800; color:#0F172A;">
        INFIX AIRLENS <span style="color:#059669;">| Family &amp; Community Air Assistant</span>
    </div>
    <div style="font-size:13px; color:#475569;">
        Grounded in Databricks Gold Serving Tables (<code>gold_air_status_now</code>, <code>gold_best_windows</code>, <code>gold_grap_status</code>, <code>gold_outlook_48h</code>) + Deterministic Exposure Math
    </div>
</div>
""", unsafe_allow_html=True)

# --- Step 1: Under-1-Minute Household Profile Onboarding ---
with st.expander("👨👩👧 Household & Lifestyle Profile (Tailors Routines, Indoor Hacks & Impact Math)", expanded=True):
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        from assistant.tools.location_resolver import load_all_cities, resolve_location
        all_city_names = [c["city_name"] for c in load_all_cities()]
        pin_input = st.text_input("Pincode (optional, e.g. 226001)", value="")
        if pin_input.strip():
            city = resolve_location(pin_input)["resolved_city"]
            st.caption(f"Resolved PIN {pin_input} → **{city}**")
        else:
            city = st.selectbox("City (25 Monitored Cities)", all_city_names, index=0)
    with p2:
        vuln = st.multiselect("Household Members", ["Child under 12", "Elderly (60+)", "Asthma / Cardiac"], default=["Child under 12"])
    with p3:
        purifier_status = st.selectbox("Indoor Filtration", ["No Purifier (₹0 / DIY hacks first)", "HEPA Purifier Available"])
    with p4:
        commute_mode = st.selectbox("Daily Commute", ["petrol_car", "petrol_two_wheeler", "metro_electric", "cng_bus"])

profile = {
    "city": city,
    "has_child_under_12": "Child under 12" in vuln,
    "has_elderly": "Elderly (60+)" in vuln,
    "has_asthma": "Asthma / Cardiac" in vuln,
    "has_purifier": purifier_status.startswith("HEPA"),
    "commute_mode": commute_mode,
}

# Fetch live Gold serving data
status = get_air_status(city)
windows = find_best_windows(city)
grap = get_grap_status(city)
outlook = get_outlook_48h(city)

aqi_val = int(status.get("aqi_now", 307))
cat_val = status.get("category", "Very Poor")
dom_poll = status.get("dominant_pollutant", "PM2.5")
pm25_out = float(status.get("pm25_ugm3", 128.0))

# --- Step 2: Today's AirPlan Hero Strip ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Current City AQI", f"{aqi_val} ({cat_val})", f"Dominant: {dom_poll}")
c2.metric("Cleanest Outdoor Window", str(windows.get("best_window", "04:00–06:00 IST")), f"Est. AQI ~{windows.get('best_aqi', '')}")
c3.metric("Avoid Peak Inversion", str(windows.get("worst_window", "22:00–24:00 IST")), f"Peak AQI ~{windows.get('worst_aqi', '')}")
c4.metric("48h Forecast Range", f"{outlook['min_forecast_aqi']:.0f} – {outlook['max_forecast_aqi']:.0f}", grap.get("grap_stage", "Non-NCR"))

if grap.get("grap_applicable", True) and "grap_stage" in grap:
    st.warning(f"**Active Delhi-NCR CAQM GRAP Status ({city}):** {grap['grap_stage']} — Prioritize public transit/carpool, avoid open waste/biomass burning, and keep children/elderly indoors during peak inversion hours. `[SRC_CAQM_GRAP]`")

tab_plan, tab_chat, tab_comm = st.tabs([
    "📋 Today's AirPlan & What-If Impact Calculators",
    "💬 Bilingual Cited Assistant (English / हिन्दी)",
    "🏘️ Community & RWA Impact Mode",
])

with tab_plan:
    left, right = st.columns([1.15, 1.0])

    with left:
        st.subheader("1. Indoor Air Quality Simulator (Deterministic Mass-Balance)")
        fix_choice = st.radio(
            "Select Indoor Intervention Tier:",
            [
                "₹0 Hack: Damp-towel / foam tape bedroom door & window gap sealing",
                "₹500 DIY: Box-Fan + MERV-13 Corsi-Rosenthal filter cube",
                "₹5,000+ Device: Closed bedroom HEPA purifier (Sleep/Auto mode)",
            ],
        )
        scen_map = {
            "₹0": "windows_closed_sealed_diy",
            "₹500": "windows_closed_diy_box_fan",
            "₹5,000+": "windows_closed_hepa_on",
        }
        tier_key = fix_choice.split(" ")[0]
        indoor_res = estimate_indoor_pm25(c_out_ugm3=pm25_out, improved_scenario=scen_map[tier_key])

        st.markdown(f"""
        <div class="impact-box">
            <b>Estimated Bedroom PM2.5 Drop: ~{indoor_res['estimated_reduction_pct']:.0f}%</b><br>
            Unsealed Closed Room: <b>{indoor_res['baseline_range'][0]}–{indoor_res['baseline_range'][1]} µg/m³</b> &rarr;
            With Intervention: <b>{indoor_res['improved_range'][0]}–{indoor_res['improved_range'][1]} µg/m³</b><br>
            <span style="font-size:12px; color:#166534;">Confidence: {indoor_res['confidence'].upper()} • Citation: <code>[{indoor_res['source_id']}]</code></span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🔍 Why this advice? (Data Lineage, Formula & Assumptions)"):
            st.write("**Data Source:**", status.get("source_table"))
            st.write("**Box-Model Formula:** $C_{in} = \\frac{P \\cdot a \\cdot C_{out} + S/V}{a + k + Q/V}$")
            for a in indoor_res["assumptions"]:
                st.markdown(f"- {a}")
            st.caption(indoor_res["note"])

    with right:
        st.subheader("2. Low-Emission Commute & Routine Impact")
        km_day = st.slider("Daily Round-Trip Commute Distance (km)", 4, 60, 20)
        alt_mode = st.selectbox("Switch To Cleaner Alternative", ["metro_electric", "cng_bus"])
        base_m = commute_mode if commute_mode in {"petrol_car", "petrol_two_wheeler"} else "petrol_car"
        comm_res = estimate_commute_savings(round_trip_km=float(km_day), days_per_week=5, baseline_mode=base_m, alternative_mode=alt_mode)

        st.markdown(f"""
        <div class="impact-box">
            <b>Weekly Household Emissions Saved ({base_m} &rarr; {alt_mode}):</b><br>
            • CO₂e Avoided: <b>{comm_res['co2e_saved_kg_range'][0]} – {comm_res['co2e_saved_kg_range'][1]} kg/week</b><br>
            • Local NOₓ Cut: <b>{comm_res['nox_saved_g_range'][0]} – {comm_res['nox_saved_g_range'][1]} g/week</b><br>
            • Tailpipe PM2.5 Cut: <b>{comm_res['pm25_saved_g_range'][0]} – {comm_res['pm25_saved_g_range'][1]} g/week</b><br>
            <span style="font-size:12px; color:#166534;">Citation: <code>[{comm_res['source_id']}]</code></span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### Recommended Actions Catalog (`data/ref/actions_catalog.csv`)")
        cat_df = pd.read_csv(ROOT / "data" / "ref" / "actions_catalog.csv")
        st.dataframe(cat_df[["action_id", "cost_tier", "title", "target_pollutant", "source_id"]], use_container_width=True, hide_index=True, height=220)

with tab_chat:
    st.subheader("Ask Infix AirLens (Grounded in Gold Tables + CPCB/CAQM Guidance)")
    st.caption("Try asking in English or Hindi/Hinglish — e.g. *'Bachche ko evening mein park le ja sakte hain?'* or *'Give me a ₹0 bedroom fix for tonight'*")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                with st.expander("🔍 Why this advice? (Tools & Citations)"):
                    st.json(msg["meta"])

    user_q = st.chat_input("Ask about outdoor timing, indoor hacks, masks, GRAP rules, or commute impact...")
    if user_q:
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)

        with st.chat_message("assistant"):
            with st.spinner("Checking live Gold tables & CPCB/CAQM guidelines..."):
                res = run_airlens_assistant(user_q, profile=profile)
            st.markdown(res["answer"])
            meta_info = {
                "intent": res["intent"],
                "tools_called": res["tool_calls_used"],
                "citations": res["citations"],
                "safety_escalated": res["safety_flag"],
            }
            with st.expander("🔍 Why this advice? (Tools & Citations)"):
                st.json(meta_info)
            st.session_state.chat_history.append({"role": "assistant", "content": res["answer"], "meta": meta_info})

with tab_comm:
    st.subheader("Apartment Society / Ward Collective Action Simulator")
    flats = st.slider("Participating Households in Society / RWA", 20, 500, 100, step=10)
    shift_pct = st.slider("% of Households Shifting 2 Commute Days/Week to Metro/Carpool", 10, 100, 40, step=10)
    active_flats = int(flats * (shift_pct / 100.0))
    soc_comm = estimate_commute_savings(round_trip_km=20.0, days_per_week=2, baseline_mode="petrol_car", alternative_mode="metro_electric")

    m1, m2, m3 = st.columns(3)
    m1.metric("Participating Commuters", f"{active_flats} households")
    m2.metric("Weekly Community CO₂e Cut", f"{soc_comm['co2e_saved_kg_range'][0]*active_flats:,.0f} – {soc_comm['co2e_saved_kg_range'][1]*active_flats:,.0f} kg")
    m3.metric("Weekly Local NOₓ Avoided", f"{(soc_comm['nox_saved_g_range'][0]*active_flats)/1000:,.2f} – {(soc_comm['nox_saved_g_range'][1]*active_flats)/1000:,.2f} kg")
    st.info("Collective RWA Playbook: Ban open dry-leaf burning by horticulture staff (`ACT_10`), sprinkle recycled STP water on unpaved entry lanes at 07:30 IST, and provide electric heaters to night security guards during GRAP Stage II–IV. `[SRC_CAQM_GRAP]`")
