import math
from pathlib import Path
import yaml

CITIES_YAML = Path(__file__).resolve().parents[2] / "config" / "cities.yaml"

# Indian 3-digit PIN prefix -> City mapping for fast offline/online resolution
PIN_PREFIX_MAP = {
    "110": "Delhi", "122": "Gurugram", "201": "Noida", "121": "Faridabad",
    "226": "Lucknow", "208": "Kanpur", "221": "Varanasi", "800": "Patna",
    "160": "Chandigarh", "143": "Amritsar", "302": "Jaipur",
    "400": "Mumbai", "411": "Pune", "440": "Nagpur", "380": "Ahmedabad", "462": "Bhopal",
    "560": "Bengaluru", "500": "Hyderabad", "600": "Chennai", "530": "Visakhapatnam", "682": "Kochi",
    "700": "Kolkata", "751": "Bhubaneswar", "781": "Guwahati",
}

def load_all_cities() -> list[dict]:
    data = yaml.safe_load(CITIES_YAML.read_text(encoding="utf-8"))
    return data.get("cities", [])

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)

def resolve_location(query_or_pincode: str) -> dict:
    """Resolve a city name, alias, or 6-digit Indian pincode to the nearest monitored AirLens city."""
    raw = query_or_pincode.strip()
    cities = load_all_cities()
    by_name = {c["city_name"].lower(): c for c in cities}
    aliases = {"bangalore": "bengaluru", "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai", "gurgaon": "gurugram", "vizag": "visakhapatnam", "cochin": "kochi"}

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 6 and digits[:3] in PIN_PREFIX_MAP:
        matched_name = PIN_PREFIX_MAP[digits[:3]]
        c = by_name[matched_name.lower()]
        return {"resolved_city": c["city_name"], "state": c["state"], "region": c["region"], "ncap_city": c.get("ncap_city", True), "matched_via": f"pincode_{digits}"}

    key = aliases.get(raw.lower(), raw.lower())
    if key in by_name:
        c = by_name[key]
        return {"resolved_city": c["city_name"], "state": c["state"], "region": c["region"], "ncap_city": c.get("ncap_city", True), "matched_via": "city_name"}

    # Default fallback
    return {"resolved_city": "Delhi", "state": "Delhi", "region": "Delhi NCR", "ncap_city": True, "matched_via": "default_fallback"}
