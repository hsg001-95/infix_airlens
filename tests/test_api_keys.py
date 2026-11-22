import os
import requests
from dotenv import load_dotenv

load_dotenv()

tests = {
    "WAQI (Delhi)": (f"https://api.waqi.info/feed/delhi/?token={os.getenv('WAQI_API_TOKEN')}", 15),
    "OpenWeather (Delhi)": (f"https://api.openweathermap.org/data/2.5/weather?lat=28.61&lon=77.23&appid={os.getenv('OPENWEATHER_API_KEY')}&units=metric", 15),
    "Open-Meteo Backup": ("https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.23&current_weather=true", 15),
    "data.gov.in CPCB": (f"https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69?api-key={os.getenv('DATAGOV_API_KEY')}&format=json&limit=5", 45),
    "NASA FIRMS (India bbox)": (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{os.getenv('NASA_FIRMS_MAP_KEY')}/VIIRS_SNPP_NRT/73,28,78,33/1", 20)
}

for name, (url, t) in tests.items():
    try:
        r = requests.get(url, timeout=t)
        snippet = r.text[:120].replace("\n", " ")
        print(f"[{r.status_code}] {name}: {snippet}")
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
