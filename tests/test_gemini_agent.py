import os
from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv(override=True)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 1. Mock deterministic tools (will be wired to Databricks Gold + Impact Engine next)
def get_air_status(city: str) -> dict:
    """Fetch live CPCB AQI and dominant pollutant for an Indian city."""
    return {
        "city": city,
        "aqi_now": 368,
        "category": "Very Poor",
        "dominant_pollutant": "PM2.5",
        "pm25_ugm3": 212.0,
        "observed_at": "2026-11-24T08:30:00+05:30",
    }

def find_best_windows(city: str) -> list[dict]:
    """Return cleanest 2-hour outdoor windows for the day."""
    return [
        {"start": "13:00", "end": "15:00", "expected_aqi": 245, "reason": "Peak afternoon boundary-layer mixing"}
    ]

# 2. Structured output schema matching Section B4.3
class ActionItem(BaseModel):
    action_id: str
    title: str
    cost_tier: str
    why: str

class AirPlan(BaseModel):
    location: str
    aqi_now: int
    category: str
    best_window: str
    actions: list[ActionItem]
    disclaimer: str

# Test A: Fast Intent Router (gemini-3.5-flash-lite)
route_resp = client.models.generate_content(
    model=os.getenv("LLM_ROUTER_MODEL", "gemini-3.5-flash-lite"),
    contents="Classify intent into [data_question, plan_request, indoor_hack, emergency]: 'My kid has football at 5pm in Delhi, is it safe?'",
)
print("Router output:", route_resp.text.strip())

# Test B: Tool-Calling Agent (gemini-3.5-flash)
tool_resp = client.models.generate_content(
    model=os.getenv("LLM_PRIMARY_MODEL", "gemini-3.5-flash"),
    contents="Check Delhi air quality and best outdoor window today for a family with a 9-year-old child.",
    config=types.GenerateContentConfig(
        system_instruction="You are Infix AirLens, a grounded family air quality assistant. Always call tools for AQI numbers. Never guess.",
        tools=[get_air_status, find_best_windows],
        temperature=0.1,
    ),
)
print("\nTool-grounded answer:\n", tool_resp.text)

# Test C: Enforced Pydantic Schema Output
plan_resp = client.models.generate_content(
    model=os.getenv("LLM_PRIMARY_MODEL", "gemini-3.5-flash"),
    contents=f"Convert this grounded advice into the required AirPlan JSON schema:\n{tool_resp.text}",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AirPlan,
    ),
)
parsed_plan = AirPlan.model_validate_json(plan_resp.text)
print("\nValidated AirPlan JSON:\n", parsed_plan.model_dump_json(indent=2))
