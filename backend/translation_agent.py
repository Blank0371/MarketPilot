"""Translation agent (Block 3) for MarketPilot.

The LLM input layer. Two operations, both prompt-driven against an LLM hosted on
**Featherless** (OpenAI-compatible chat API). The LLM only *structures language* —
it never computes results or makes the decision (that is Block 4).

Operation A — idea -> descriptions (FLOW_AND_AGENTS.md §4.1a):
    extract_descriptions(user_input) -> list[str]
    Injects the 7 standardized factors and rephrases each to fit the user's
    business/location.

Operation B — corrected descriptions -> keywords -> Data-Engineer (§4.1b):
    descriptions_to_keywords(descriptions) -> list[str]   (3–6 keywords)
    confirm_descriptions(descriptions) -> dict            (keywords + DE call)

HTTP surface (canonical routes, ARCHITECTURE.md §5):
    POST /api/extract   { userInput }      -> { descriptions: [...] }
    POST /api/confirm   { descriptions }   -> Data-Engineer response (+ translation)

Resilience (CLAUDE.md §4, BLOCK3.md §5): strict-JSON prompting, parse defensively,
retry once with a stricter prompt, then fall back to deterministic mock output so
the rest of the team is never blocked when the API key or network is missing.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter

import httpx
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("marketpilot.translation_agent")

# ---------------------------------------------------------------------------
# Configuration (env, never hard-coded — CLAUDE.md / BLOCK3.md §5)
# ---------------------------------------------------------------------------
# Featherless is OpenAI-compatible, so we hit /chat/completions with httpx and
# avoid pulling in an extra SDK dependency.
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_MODEL = os.getenv("FEATHERLESS_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
_LLM_TIMEOUT_S = 30.0
_DATA_ENGINEER_TIMEOUT_S = 30.0

# The 7 standardized factors. The translation LLM rephrases each one to fit the
# user's business; a new business reuses the same factors with new wording — this
# is what makes MarketPilot generic (CLAUDE.md §3, FLOW_AND_AGENTS.md §3).
STANDARDIZED_FACTORS: tuple[str, ...] = (
    "rent",
    "staff costs",
    "location foot traffic",
    "average basket price",
    "margin",
    "seasonality",
    "tourism dependency",
)

# Generic rephrasings used by the mock fallback (no key / malformed LLM output).
# {loc} = " in <location>" or "", {biz} = detected business or a generic phrase.
_FALLBACK_TEMPLATES: dict[str, str] = {
    "rent": "Average rent for a small retail location{loc}",
    "staff costs": "Typical staff costs for a small retail business{loc}",
    "location foot traffic": "Monthly foot traffic{loc}",
    "average basket price": "Average basket price per customer for {biz}",
    "margin": "Typical gross margin for {biz}",
    "seasonality": "Seasonal demand pattern for {biz} across the year",
    "tourism dependency": "Tourism dependency of retail{loc}",
}

# Demand-driver terms used to pad keyword lists up to the 3–6 minimum.
_DEMAND_TERMS: tuple[str, ...] = ("seasonality", "tourism", "weather", "demand", "revenue")

# Filler words dropped before deriving fallback keywords from descriptions.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "average", "small", "retail", "location", "typical", "monthly", "business",
        "this", "that", "with", "from", "into", "over", "across", "year", "years",
        "their", "there", "type", "kind", "sort", "area", "customer", "customers",
        "based", "could", "affect", "success", "described", "across", "annual",
    }
)


# ---------------------------------------------------------------------------
# Featherless client (modular — BLOCK3.md §5)
# ---------------------------------------------------------------------------
class FeatherlessClient:
    """Thin OpenAI-compatible chat client for Featherless.

    The API key is read from ``FEATHERLESS_API_KEY`` at construction time so tests
    can toggle availability by setting/clearing the env var. When no key is set
    the client reports ``available == False`` and callers use the mock fallback.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = _LLM_TIMEOUT_S,
    ) -> None:
        self.api_key = api_key or os.getenv("FEATHERLESS_API_KEY")
        self.base_url = (base_url or FEATHERLESS_BASE_URL).rstrip("/")
        self.model = model or FEATHERLESS_MODEL
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 900) -> str:
        """Return the assistant message content for a system+user prompt pair."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Strict-JSON parsing helpers
# ---------------------------------------------------------------------------
def _parse_json_object(text: str) -> dict:
    """Parse the first JSON object out of an LLM response.

    Tolerates markdown fences and leading/trailing prose by extracting the
    outermost ``{...}`` span. Raises ``ValueError`` if nothing parseable is found,
    which triggers the retry/fallback path.
    """
    if not text or not text.strip():
        raise ValueError("empty LLM response")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in LLM response")
    return json.loads(stripped[start : end + 1])


def _coerce_str_list(value: object) -> list[str]:
    """Return a clean list of non-empty trimmed strings (drops anything else)."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _llm_json(client: FeatherlessClient, system: str, user: str, stricter_user: str, *, max_tokens: int) -> dict:
    """Call the LLM and parse strict JSON, retrying once with a stricter prompt.

    Retries on both transport errors and malformed JSON. Raises after the second
    failure so the caller can fall back to mock output.
    """
    last_error: Exception | None = None
    for attempt, prompt in enumerate((user, stricter_user), start=1):
        try:
            raw = client.chat(system, prompt, max_tokens=max_tokens)
            return _parse_json_object(raw)
        except Exception as exc:  # network error or unparseable JSON
            last_error = exc
            logger.warning("Featherless attempt %d failed: %s", attempt, exc)
    raise last_error or RuntimeError("LLM call failed")


# ---------------------------------------------------------------------------
# Lightweight text extraction (mock fallback + statistic-title synthesis)
# ---------------------------------------------------------------------------
# "in <Capitalized phrase>" — e.g. "in Vienna's 1st district" -> "Vienna's 1st district".
_LOCATION_RE = re.compile(r"\bin\s+([A-Z][A-Za-z'’.]+(?:\s+[\w'’.]+){0,4})")
# "open/start/... [a] <business> in" -> the business phrase.
_BUSINESS_RE = re.compile(
    r"\b(?:open|start|launch|build|run|opening|starting|create|set\s+up)\s+"
    r"(?:an?\s+|my\s+|the\s+)?([a-z][\w'’ -]*?)\s+(?:in|near|at|on)\b",
    re.IGNORECASE,
)


def _detect_location(text: str) -> str:
    if not text:
        return ""
    match = _LOCATION_RE.search(text)
    return match.group(1).strip().rstrip(".") if match else ""


def _detect_business(text: str) -> str:
    if not text:
        return ""
    match = _BUSINESS_RE.search(text)
    return match.group(1).strip().lower() if match else ""


def _fallback_descriptions(user_input: str) -> list[str]:
    """Deterministic rephrasing of all 7 factors when the LLM is unavailable."""
    location = _detect_location(user_input)
    business = _detect_business(user_input) or "this type of retail business"
    loc_suffix = f" in {location}" if location else ""
    return [_FALLBACK_TEMPLATES[factor].format(loc=loc_suffix, biz=business) for factor in STANDARDIZED_FACTORS]


def _derive_keywords(descriptions: list[str]) -> list[str]:
    """Rank candidate keywords by frequency across the descriptions."""
    counts: Counter[str] = Counter()
    for description in descriptions:
        for token in re.findall(r"[a-zA-Z]+", str(description).lower()):
            if len(token) > 3 and token not in _STOPWORDS:
                counts[token] += 1
    return [word for word, _ in counts.most_common()]


def _clamp_keywords(keywords: list[str], descriptions: list[str] | None = None) -> list[str]:
    """Dedupe, lowercase, and force the list into the contractual 3–6 range."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    if len(cleaned) < 3:
        for candidate in (*_derive_keywords(descriptions or []), *_DEMAND_TERMS):
            if len(cleaned) >= 3:
                break
            if candidate not in seen:
                seen.add(candidate)
                cleaned.append(candidate)
    return cleaned[:6]


def _synthesize_title(descriptions: list[str], user_input: str | None = None) -> str:
    """Build a concise statistic title for the Data-Engineer request."""
    # Scan candidates individually: joining descriptions would let the location
    # regex spill across boundaries (e.g. "...1st district Typical staff").
    location = ""
    for candidate in ([user_input] if user_input else descriptions):
        location = _detect_location(candidate or "")
        if location:
            break
    business = _detect_business(user_input) if user_input else ""
    if business and location:
        return f"Average revenue of {business} in {location}"
    if location:
        return f"Average revenue for the described business in {location}"
    if business:
        return f"Average revenue of {business}"
    return "Average revenue for the described business"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
_A_SYSTEM = (
    "You are a precise market-research assistant for MarketPilot, a business-forecasting tool. "
    "You convert a business idea into concrete, searchable descriptions of quantifiable factors. "
    "You ALWAYS return only strict JSON — no prose, no markdown."
)

_B_SYSTEM = (
    "You extract concise search keywords and a statistic title from factor descriptions for a "
    "forecasting tool. You ALWAYS return only strict JSON — no prose, no markdown."
)

_STRICT_SUFFIX = (
    "\n\nIMPORTANT: your previous answer was not valid JSON. Return ONLY a single JSON object, "
    "with no markdown fences and no commentary."
)


def _a_user(user_input: str) -> str:
    factors = "\n".join(f"{i}. {name}" for i, name in enumerate(STANDARDIZED_FACTORS, start=1))
    return (
        f"Business idea: {user_input}\n\n"
        "Rephrase EACH of the following standardized factors into a concrete, searchable "
        "description tailored to this business and its location. Keep the same order. Each "
        'description should read like a statistic you could look up, e.g. "Average rent for a '
        'small retail location in Vienna\'s 1st district".\n\n'
        f"Factors (in order):\n{factors}\n\n"
        'Return ONLY this JSON, nothing else:\n'
        '{"descriptions": ["...", "...", "...", "...", "...", "...", "..."]}\n'
        f"The \"descriptions\" array must have exactly {len(STANDARDIZED_FACTORS)} items, "
        "one per factor in the order above."
    )


def _b_user(descriptions: list[str]) -> str:
    numbered = "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions, start=1))
    return (
        "These are the confirmed factor descriptions for a business forecast:\n"
        f"{numbered}\n\n"
        "1. Extract 3 to 6 short keywords (single words or short phrases) that are influential "
        "for the statistics these descriptions analyze. Prefer demand drivers such as the product "
        "category, the city, seasonality, tourism, and weather.\n"
        "2. Write a concise statistic title describing the core revenue series to look up, e.g. "
        '"Average revenue of ice cream shops in Vienna".\n\n'
        "Return ONLY this JSON, nothing else:\n"
        '{"keywords": ["...", "..."], "statistic_title": "..."}'
    )


# ---------------------------------------------------------------------------
# Operation A — idea -> descriptions
# ---------------------------------------------------------------------------
def extract_descriptions(user_input: str, *, client: FeatherlessClient | None = None) -> list[str]:
    """Turn a free-text business idea into rephrased factor descriptions.

    Returns the 7 standardized factors rephrased to fit ``user_input``. Falls back
    to deterministic mock descriptions when the LLM is unavailable or misbehaves.
    """
    user_input = (user_input or "").strip()
    if not user_input:
        return _fallback_descriptions("")

    client = client or FeatherlessClient()
    if client.available:
        try:
            data = _llm_json(client, _A_SYSTEM, _a_user(user_input), _a_user(user_input) + _STRICT_SUFFIX, max_tokens=900)
            descriptions = _coerce_str_list(data.get("descriptions"))
            if len(descriptions) >= 3:
                return descriptions
            logger.warning("LLM returned %d descriptions (<3); using mock fallback", len(descriptions))
        except Exception as exc:
            logger.warning("description extraction failed (%s); using mock fallback", exc)
    else:
        logger.info("FEATHERLESS_API_KEY not set; returning mock descriptions")
    return _fallback_descriptions(user_input)


# ---------------------------------------------------------------------------
# Operation B — corrected descriptions -> keywords (+ statistic title)
# ---------------------------------------------------------------------------
def _keywords_and_title(descriptions: list[str], *, client: FeatherlessClient | None = None) -> tuple[list[str], str]:
    descriptions = _coerce_str_list(descriptions)
    if not descriptions:
        return _clamp_keywords([]), "Average revenue for the described business"

    client = client or FeatherlessClient()
    if client.available:
        try:
            data = _llm_json(client, _B_SYSTEM, _b_user(descriptions), _b_user(descriptions) + _STRICT_SUFFIX, max_tokens=300)
            keywords = _clamp_keywords(_coerce_str_list(data.get("keywords")), descriptions)
            title = str(data.get("statistic_title") or "").strip() or _synthesize_title(descriptions)
            if len(keywords) >= 3:
                return keywords, title
            logger.warning("LLM returned too few keywords; using mock fallback")
        except Exception as exc:
            logger.warning("keyword extraction failed (%s); using mock fallback", exc)
    else:
        logger.info("FEATHERLESS_API_KEY not set; returning mock keywords")
    return _clamp_keywords(_derive_keywords(descriptions), descriptions), _synthesize_title(descriptions)


def descriptions_to_keywords(descriptions: list[str], *, client: FeatherlessClient | None = None) -> list[str]:
    """Extract 3–6 influential keywords from the corrected descriptions."""
    keywords, _title = _keywords_and_title(descriptions, client=client)
    return keywords


# ---------------------------------------------------------------------------
# Data-Engineer call (Block 3 -> Block 2)
# ---------------------------------------------------------------------------
def call_data_engineer(description: str, key_word: list[str]) -> dict:
    """Call the Data-Engineer agent with the canonical ``{description, keyWord}``.

    Uses HTTP when ``DATA_ENGINEER_URL`` is set (microservice deployment), and
    otherwise calls ``get_timeseries`` in-process (monolith default). On HTTP
    failure it falls back to the in-process call so the demo never blocks.
    """
    payload = {"description": description, "keyWord": list(key_word)}  # camelCase per the contract
    base_url = os.getenv("DATA_ENGINEER_URL")
    if base_url:
        try:
            with httpx.Client(timeout=_DATA_ENGINEER_TIMEOUT_S) as client:
                response = client.post(f"{base_url.rstrip('/')}/data/timeseries", json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("Data-Engineer HTTP call failed (%s); falling back to in-process", exc)

    from backend.data_engineer import get_timeseries

    return get_timeseries(description, key_word)


def confirm_descriptions(descriptions: list[str], *, client: FeatherlessClient | None = None) -> dict:
    """Operation B end-to-end: extract keywords, then call the Data-Engineer.

    Returns the Data-Engineer response unchanged (passed upward per FLOW §4.1b),
    plus a ``translation`` block exposing the keywords and synthesized statistic
    title for transparency on the dashboard.
    """
    keywords, title = _keywords_and_title(descriptions, client=client)
    data_engineer_response = call_data_engineer(title, keywords)
    return {**data_engineer_response, "translation": {"keywords": keywords, "statistic_description": title}}


# ---------------------------------------------------------------------------
# Wire models (match the contract field names exactly)
# ---------------------------------------------------------------------------
class ExtractRequest(BaseModel):
    userInput: str = Field(..., min_length=1)


class ExtractResponse(BaseModel):
    descriptions: list[str]


class ConfirmRequest(BaseModel):
    descriptions: list[str] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
router = APIRouter(tags=["translation"])


@router.post("/api/extract", response_model=ExtractResponse)
def post_extract(request: ExtractRequest) -> JSONResponse:
    """POST /api/extract — idea -> standardized factor descriptions (Operation A)."""
    try:
        descriptions = extract_descriptions(request.userInput)
        return JSONResponse(content={"descriptions": descriptions})
    except Exception as exc:  # defensive: keep the demo alive with a clean error
        logger.exception("extract_descriptions failed")
        return JSONResponse(status_code=500, content={"error": "translation_extract_failed", "detail": str(exc)})


@router.post("/api/confirm")
def post_confirm(request: ConfirmRequest) -> JSONResponse:
    """POST /api/confirm — corrected descriptions -> keywords -> Data-Engineer (Operation B).

    Returns the Data-Engineer response synchronously. In the assembled orchestrator
    (backend/main.py) this route may instead kick off the async Sybilion pipeline
    and return ``{ job_id }`` (ARCHITECTURE.md §4); Block 3 owns the translation +
    Data-Engineer call, which is what this surface exposes for standalone use.
    """
    try:
        result = confirm_descriptions(request.descriptions)
        return JSONResponse(content=result)
    except Exception as exc:  # defensive: keep the demo alive with a clean error
        logger.exception("confirm_descriptions failed")
        return JSONResponse(status_code=500, content={"error": "translation_confirm_failed", "detail": str(exc)})


# Standalone app so Block 3 runs independently: `uvicorn backend.translation_agent:app`.
# The orchestrator (backend/main.py) can instead `app.include_router(router)`.
app = FastAPI(title="MarketPilot — Translation Agent", version="1.0.0")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "translation"}


if __name__ == "__main__":  # pragma: no cover - manual run
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
