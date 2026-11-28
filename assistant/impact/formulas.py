from pathlib import Path
import pandas as pd

REF_DIR = Path(__file__).resolve().parents[2] / "data" / "ref"

def _load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(REF_DIR / name)

def estimate_indoor_pm25(
    c_out_ugm3: float,
    baseline_scenario: str = "windows_closed_unsealed",
    improved_scenario: str = "windows_closed_sealed_diy",
    room_volume_m3: float = 36.0,  # ~12x10x10 ft Indian bedroom
    indoor_source_ugh: float = 0.0,
) -> dict:
    """Steady-state mass balance: C_in = (P * a * C_out + S/V) / (a + k + Q/V)."""
    df = _load_csv("indoor_params.csv").set_index("scenario")
    b = df.loc[baseline_scenario]
    imp = df.loc[improved_scenario]

    def calc_band(row):
        # High ACH gives upper indoor infiltration; Low ACH gives lower infiltration
        c_low = (row["penetration_p"] * row["ach_low"] * c_out_ugm3 + indoor_source_ugh / room_volume_m3) / (
            row["ach_low"] + row["deposition_k"] + row["cadr_m3h"] / room_volume_m3
        )
        c_high = (row["penetration_p"] * row["ach_high"] * c_out_ugm3 + indoor_source_ugh / room_volume_m3) / (
            row["ach_high"] + row["deposition_k"] + row["cadr_m3h"] / room_volume_m3
        )
        return round(min(c_low, c_high), 1), round(max(c_low, c_high), 1)

    base_low, base_high = calc_band(b)
    imp_low, imp_high = calc_band(imp)

    base_mid = (base_low + base_high) / 2.0
    imp_mid = (imp_low + imp_high) / 2.0
    pct_drop = round(((base_mid - imp_mid) / max(base_mid, 1.0)) * 100.0, 0)

    return {
        "metric": "Estimated Indoor PM2.5 Concentration",
        "baseline_range": [base_low, base_high],
        "improved_range": [imp_low, imp_high],
        "estimated_reduction_pct": max(0.0, pct_drop),
        "unit": "µg/m³",
        "assumptions": [
            f"Outdoor PM2.5 = {c_out_ugm3:.0f} µg/m³",
            f"Room volume = {room_volume_m3:.0f} m³ (~12×10×10 ft bedroom)",
            f"Baseline: {baseline_scenario} (ACH {b['ach_low']}–{b['ach_high']}/h)",
            f"Action: {improved_scenario} (CADR {imp['cadr_m3h']:.0f} m³/h)",
        ],
        "confidence": "medium",
        "note": "Steady-state box-model estimate, not a physical sensor measurement.",
        "source_id": str(imp["source_id"]),
    }

def estimate_exposure_shift(
    c_peak_ugm3: float,
    c_clean_window_ugm3: float,
    duration_hours: float = 1.0,
    age_group: str = "child_under_12",
    activity_level: str = "moderate_outdoor",
) -> dict:
    """Inhaled dose avoided (µg PM2.5) = (C_peak - C_clean) * BR * dt."""
    df = _load_csv("exposure_params.csv")
    row = df[(df["age_group"] == age_group) & (df["activity_level"] == activity_level)].iloc[0]

    delta_c = max(0.0, c_peak_ugm3 - c_clean_window_ugm3)
    avoided_low = round(delta_c * row["br_low_m3h"] * duration_hours, 1)
    avoided_high = round(delta_c * row["br_high_m3h"] * duration_hours, 1)

    return {
        "metric": "Avoided Inhaled PM2.5 Dose",
        "low": avoided_low,
        "high": avoided_high,
        "unit": "µg PM2.5 inhaled",
        "assumptions": [
            f"Shifting {duration_hours:.1f}h of {activity_level} ({age_group}) from {c_peak_ugm3:.0f} µg/m³ to {c_clean_window_ugm3:.0f} µg/m³",
            f"Breathing rate range: {row['br_low_m3h']}–{row['br_high_m3h']} m³/h",
        ],
        "confidence": "medium",
        "source_id": str(row["source_id"]),
    }

def estimate_commute_savings(
    round_trip_km: float = 20.0,
    days_per_week: int = 5,
    baseline_mode: str = "petrol_car",
    alternative_mode: str = "metro_electric",
) -> dict:
    """Weekly avoided CO2e (kg) and local tailpipe PM2.5 / NOx (g)."""
    df = _load_csv("emission_factors.csv").set_index("mode_or_fuel")
    b = df.loc[baseline_mode]
    alt = df.loc[alternative_mode]

    weekly_km = round_trip_km * days_per_week
    co2_saved_kg = round((weekly_km * (b["co2e_g_per_unit"] - alt["co2e_g_per_unit"])) / 1000.0, 2)
    nox_saved_g = round(weekly_km * (b["nox_g_per_unit"] - alt["nox_g_per_unit"]), 2)
    pm25_saved_g = round(weekly_km * (b["pm25_g_per_unit"] - alt["pm25_g_per_unit"]), 3)

    return {
        "metric": "Weekly Commute Emissions Avoided",
        "co2e_saved_kg_range": [round(co2_saved_kg * 0.85, 2), round(co2_saved_kg * 1.15, 2)],
        "nox_saved_g_range": [round(nox_saved_g * 0.85, 2), round(nox_saved_g * 1.15, 2)],
        "pm25_saved_g_range": [round(pm25_saved_g * 0.85, 3), round(pm25_saved_g * 1.15, 3)],
        "assumptions": [
            f"{round_trip_km:.0f} km/day × {days_per_week} days/week ({weekly_km:.0f} km/week)",
            f"Switching {baseline_mode} ({b['co2e_g_per_unit']} g CO2e/km) -> {alternative_mode} ({alt['co2e_g_per_unit']} g CO2e/km)",
            "±15% uncertainty band for occupancy and traffic congestion",
        ],
        "confidence": "high",
        "source_id": str(b["source_id"]),
    }
