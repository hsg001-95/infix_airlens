from assistant.impact.formulas import (
    estimate_indoor_pm25,
    estimate_exposure_shift,
    estimate_commute_savings,
)

def test_indoor_hepa_reduces_pm25():
    res = estimate_indoor_pm25(c_out_ugm3=250.0, baseline_scenario="windows_closed_unsealed", improved_scenario="windows_closed_hepa_on")
    assert res["improved_range"][1] < res["baseline_range"][0]
    assert res["estimated_reduction_pct"] >= 60.0

def test_exposure_shift_positive():
    res = estimate_exposure_shift(c_peak_ugm3=240.0, c_clean_window_ugm3=130.0, duration_hours=1.0, age_group="child_under_12")
    assert res["low"] > 0 and res["high"] > res["low"]

def test_commute_savings_metro_vs_car():
    res = estimate_commute_savings(round_trip_km=20.0, days_per_week=5, baseline_mode="petrol_car", alternative_mode="metro_electric")
    assert res["co2e_saved_kg_range"][0] > 10.0
