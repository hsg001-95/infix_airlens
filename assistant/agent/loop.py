import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types
from assistant.tools.air_tools import (
    resolve_location,
    get_air_status,
    find_best_windows,
    get_grap_status,
    get_outlook_48h,
    retrieve_guidance,
    estimate_indoor_pm25,
    estimate_exposure_shift,
    estimate_commute_savings,
)

load_dotenv(override=True)

SYSTEM_PROMPT = """You are Infix AirLens, a calm, practical, non-alarmist GenAI air-quality advisor for Indian families and communities.
STRICT GROUNDING & SAFETY RULES:
1. NEVER invent AQI values, pollutant levels, or impact reductions. ALWAYS call tools (`get_air_status`, `find_best_windows`, `get_grap_status`, `get_outlook_48h`, `estimate_indoor_pm25`, `estimate_exposure_shift`, `estimate_commute_savings`) for any number.
2. ALWAYS call `retrieve_guidance` before making health, mask, GRAP, or indoor air safety claims, and cite the exact `source_id` (e.g., [SRC_CPCB_ADVISORY], [SRC_CAQM_GRAP], [SRC_EPA_INDOOR]).
3. EQUITY FIRST: Prioritize ₹0 and low-cost actions before suggesting expensive purifiers.
4. SAFETY GUARDRAILS:
   - Never diagnose or prescribe medication.
   - If the user reports severe breathlessness, chest pain, worsening wheezing, fainting, or a child struggling to breathe, immediately advise urgent medical care.
   - Never advise sealing a room while burning coal, charcoal (sigri/angithi), wood, or unvented gas/kerosene heaters (carbon monoxide risk).
   - Never recommend ozone generators or claim houseplants clean room air.
5. LANGUAGE: Match the user's language (English, Hindi, or Hinglish) naturally and clearly."""

EMERGENCY_KEYWORDS = {"chest pain", "can't breathe", "cannot breathe", "severe breathlessness", "fainting", "blue lips", "saans nahi"}

class AgentResponse(BaseModel):
    intent: str
    answer: str
    tool_calls_used: list[str]
    citations: list[str]
    safety_flag: bool

def _get_client() -> genai.Client:
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def _generate_with_retry(client: genai.Client, model: str, contents, config: types.GenerateContentConfig, max_retries: int = 3):
    import time
    last_err = None
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            last_err = e
            err_str = str(e)
            if any(w in err_str for w in ["503", "429", "UNAVAILABLE", "high demand", "ResourceExhausted"]):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise e
    if last_err:
        raise last_err

def classify_intent(query: str) -> str:
    q_low = query.lower()
    if any(k in q_low for k in EMERGENCY_KEYWORDS):
        return "emergency"
    client = _get_client()
    try:
        resp = _generate_with_retry(
            client=client,
            model=os.getenv("LLM_ROUTER_MODEL", "gemini-3.5-flash-lite"),
            contents=(
                "Classify into ONE label from [data_question, plan_request, indoor_hack, alternative, health_concern, off_topic]: "
                f"'{query}'. Return ONLY the label."
            ),
            config=types.GenerateContentConfig(temperature=0.0),
        )
        label = (resp.text or "plan_request").strip().lower()
    except Exception:
        label = "plan_request"
    allowed = {"data_question", "plan_request", "indoor_hack", "alternative", "health_concern", "off_topic"}
    return label if label in allowed else "plan_request"

def run_airlens_assistant(query: str, profile: dict | None = None) -> dict:
    intent = classify_intent(query)
    if intent == "emergency":
        return {
            "intent": "emergency",
            "answer": (
                "If anyone is experiencing chest pain, severe breathlessness, worsening wheezing, or fainting, "
                "please seek urgent medical care or call emergency services (112 / 108 in India) immediately. "
                "Move the person to clean indoor air while waiting for medical help. [SRC_CPCB_ADVISORY]"
            ),
            "tool_calls_used": [],
            "citations": ["SRC_CPCB_ADVISORY"],
            "safety_flag": True,
        }

    profile_str = json.dumps(profile or {"city": "Delhi", "has_child_under_12": True, "has_purifier": False})
    prompt = f"Household Profile Tags: {profile_str}\nUser Question: {query}"

    tools = [
        resolve_location,
        get_air_status,
        find_best_windows,
        get_grap_status,
        get_outlook_48h,
        retrieve_guidance,
        estimate_indoor_pm25,
        estimate_exposure_shift,
        estimate_commute_savings,
    ]

    client = _get_client()
    response = _generate_with_retry(
        client=client,
        model=os.getenv("LLM_PRIMARY_MODEL", "gemini-3.5-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tools,
            temperature=0.15,
        ),
    )

    answer_text = response.text or "I could not generate a grounded response right now. Please try again."

    # Extract tool names & citations for the "Why this advice?" transparency drawer
    used_tools = []
    if response.automatic_function_calling_history:
        for msg in response.automatic_function_calling_history:
            for part in getattr(msg, "parts", []) or []:
                if getattr(part, "function_call", None):
                    used_tools.append(part.function_call.name)

    known_sources = ["SRC_CPCB_ADVISORY", "SRC_CAQM_GRAP", "SRC_EPA_INDOOR", "SRC_WHO_AQG", "SRC_ICCT_EMISSIONS"]
    citations = [s for s in known_sources if s in answer_text]

    return {
        "intent": intent,
        "answer": answer_text,
        "tool_calls_used": list(dict.fromkeys(used_tools)),
        "citations": citations,
        "safety_flag": False,
    }
