import json
import os

base = os.path.expanduser("~/infix-airlens/pbip_report/Infix_AirLens.Report")
theme_dir = f"{base}/StaticResources/SharedResources/BaseThemes"
os.makedirs(theme_dir, exist_ok=True)

# 1. Light Executive CPCB Palette Theme
theme = {
    "name": "InfixAirLensLightExec",
    "dataColors": [
        "#0284C7",  # Primary Ocean Cyan
        "#E11D48",  # Severe Crimson
        "#EA580C",  # Very Poor Orange
        "#D97706",  # Poor Amber
        "#059669",  # Good Emerald
        "#7C3AED",  # Royal Violet
        "#0D9488",  # Teal
        "#475569"   # Slate
    ],
    "background": "#F4F7FB",
    "foreground": "#0F172A",
    "tableAccent": "#0284C7",
    "visualStyles": {
        "*": {
            "*": {
                "background": [{"color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": "#E2E8F0"}}, "radius": 12}],
                "dropShadow": [{
                    "show": True,
                    "color": {"solid": {"color": "#94A3B8"}},
                    "position": "Outer",
                    "preset": "BottomRight"
                }],
                "title": [{
                    "show": True,
                    "fontColor": {"solid": {"color": "#0F172A"}},
                    "fontSize": 11,
                    "fontFamily": "Segoe UI Semibold"
                }]
            }
        },
        "page": {
            "*": {
                "background": [{"color": {"solid": {"color": "#F4F7FB"}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": "#E2E8F0"}}, "transparency": 0}]
            }
        }
    }
}

theme_path = f"{theme_dir}/InfixAirLensLightExec.json"
with open(theme_path, "w", encoding="utf-8") as f:
    json.dump(theme, f, indent=2)

# 2. Helper to build visual containers
def make_visual(name, vtype, x, y, w, h, title_text, projections):
    config = {
        "name": name,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 1000, "width": w, "height": h}}],
        "singleVisual": {
            "visualType": vtype,
            "projections": projections,
            "vcObjects": {
                "title": [{
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{title_text}'"}}}
                    }
                }]
            }
        }
    }
    return {"x": x, "y": y, "z": 1000, "width": w, "height": h, "config": json.dumps(config)}

# 3. Auto-layout Page 1 (Executive Overview + 3D Map) & Page 2 (Drivers + Forecast)
page1_visuals = [
    make_visual("slicer_city", "slicer", 20, 15, 620, 75, "Select City", {
        "Values": [{"queryRef": "gold_pollution_hotspot_ranking.city"}]
    }),
    make_visual("kpi_aqi", "card", 660, 15, 190, 95, "Mean Daily AQI", {
        "Values": [{"queryRef": "Avg(gold_city_daily_aqi.daily_aqi)"}]
    }),
    make_visual("kpi_hotspot", "card", 865, 15, 190, 95, "Peak Hotspot Index", {
        "Values": [{"queryRef": "Max(gold_pollution_hotspot_ranking.hotspot_index)"}]
    }),
    make_visual("kpi_alerts", "card", 1070, 15, 190, 95, "High/Critical Alerts", {
        "Values": [{"queryRef": "Count(gold_aqi_alerts.alert_message)"}]
    }),
    make_visual("map_3d", "azureMap", 20, 125, 580, 340, "3D City Hotspot Severity Map", {
        "Category": [{"queryRef": "gold_pollution_hotspot_ranking.city"}],
        "Size": [{"queryRef": "Sum(gold_pollution_hotspot_ranking.hotspot_index)"}]
    }),
    make_visual("trend_7d", "lineChart", 615, 125, 645, 340, "7-Day Rolling AQI Trajectory", {
        "Category": [{"queryRef": "gold_city_daily_aqi.date"}],
        "Y": [{"queryRef": "Avg(gold_city_daily_aqi.rolling_7d_aqi)"}],
        "Series": [{"queryRef": "gold_pollution_hotspot_ranking.city"}]
    }),
    make_visual("alerts_tbl", "tableEx", 20, 480, 1240, 220, "Active Severe & Very Poor AQI Threshold Breaches", {
        "Values": [
            {"queryRef": "gold_aqi_alerts.date"},
            {"queryRef": "gold_aqi_alerts.city"},
            {"queryRef": "gold_aqi_alerts.daily_aqi"},
            {"queryRef": "gold_aqi_alerts.aqi_category"},
            {"queryRef": "gold_aqi_alerts.dominant_pollutant"},
            {"queryRef": "gold_aqi_alerts.severity"}
        ]
    })
]

page2_visuals = [
    make_visual("fire_lag", "lineClusteredColumnComboChart", 20, 20, 680, 320, "Punjab-Haryana Fire FRP (MW) vs Lag-1 Delhi NCR AQI", {
        "Category": [{"queryRef": "gold_fire_aqi_impact.fire_date"}],
        "ColumnY": [{"queryRef": "Sum(gold_fire_aqi_impact.total_frp_mw)"}],
        "LineY": [{"queryRef": "Avg(gold_fire_aqi_impact.ncr_aqi_lag1)"}]
    }),
    make_visual("wind_corr", "barChart", 715, 20, 545, 320, "Wind Speed Dispersion Correlation (corr_wind_pm25)", {
        "Category": [{"queryRef": "gold_weather_aqi_correlation.city"}],
        "Y": [{"queryRef": "Avg(gold_weather_aqi_correlation.corr_wind_pm25)"}]
    }),
    make_visual("forecast_line", "lineChart", 20, 355, 1240, 345, "7-Day Recursive AQI Forecast with 80% Confidence Interval", {
        "Category": [{"queryRef": "gold_aqi_forecast.forecast_date"}],
        "Y": [
            {"queryRef": "Avg(gold_aqi_forecast.predicted_aqi)"},
            {"queryRef": "Avg(gold_aqi_forecast.ci80_upper)"},
            {"queryRef": "Avg(gold_aqi_forecast.ci80_lower)"}
        ]
    })
]

report_json = {
    "config": json.dumps({
        "version": "5.51",
        "themeCollection": {
            "baseTheme": {"name": "InfixAirLensLightExec", "version": "5.51", "type": 2}
        }
    }),
    "layoutOptimization": 0,
    "resourcePackages": [{
        "resourcePackage": {
            "name": "SharedResources",
            "type": 2,
            "items": [{"type": 202, "path": "BaseThemes/InfixAirLensLightExec.json", "name": "InfixAirLensLightExec"}]
        }
    }],
    "sections": [
        {"name": "ReportSection1", "displayName": "Executive Overview", "visualContainers": page1_visuals, "width": 1280, "height": 720, "displayOption": 1},
        {"name": "ReportSection2", "displayName": "Drivers & 7-Day Forecast", "visualContainers": page2_visuals, "width": 1280, "height": 720, "displayOption": 1}
    ]
}

with open(f"{base}/report.json", "w", encoding="utf-8") as f:
    json.dump(report_json, f, indent=2)

with open(f"{base}/definition.pbir", "w", encoding="utf-8") as f:
    json.dump({"version": "4.0", "datasetReference": {"byConnection": None}}, f, indent=2)

with open(os.path.expanduser("~/infix-airlens/pbip_report/Infix_AirLens.pbip"), "w", encoding="utf-8") as f:
    json.dump({"version": "1.0", "artifacts": [{"report": {"path": "Infix_AirLens.Report"}}], "settings": {"enableAutoRecovery": True}}, f, indent=2)

print("Generated Light Theme PBIP Project at:", os.path.expanduser("~/infix-airlens/pbip_report"))
print("Theme JSON ready at:", theme_path)
