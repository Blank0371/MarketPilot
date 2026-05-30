"""Translation agent (Block 3) for MarketPilot.

Pipeline per endpoint:

  POST /api/extract  { userInput }
      LLM → 7 rephrased factor descriptions
      → { descriptions: [...] }

  POST /api/confirm  { descriptions }
      LLM → keywords + statistic title
      → Data-Engineer → timeseries
      → clean timeseries
      → Sybilion /api/v1/forecasts  (submit → poll → download artifacts)
      → LLM judgment (with session context)
      → { session_id, judgment, forecast, signals, ... }

  POST /api/refine   { sessionId, descriptions, initialDescriptions? }
      Same pipeline as /api/confirm for the new descriptions.
      Merges new timeseries with all prior session data before submitting to Sybilion.
      LLM judgment receives full conversation history → context-aware update.
      → { session_id, round, judgment, forecast, signals, ... }

  GET  /api/session/{id}   — inspect session state (no LLM/DE/Sybilion calls)
  GET  /health

Resilience: strict-JSON prompting, one retry with stricter prompt, then deterministic
mock fallback so the rest of the team is never blocked.
Sessions: in-memory, keyed by UUID, TTL configurable via SESSION_TTL_SECONDS env var.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from fastapi.middleware.cors import CORSMiddleware
import httpx
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("marketpilot.translation_agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_MODEL    = os.getenv("FEATHERLESS_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
SYBILION_BASE_URL    = os.getenv("SYBILION_BASE_URL", "https://api.sybilion.dev")

_LLM_TIMEOUT_S           = 30.0
_DATA_ENGINEER_TIMEOUT_S = 30.0
_SYBILION_SUBMIT_TIMEOUT = 30.0
_SYBILION_POLL_INTERVAL  = 8.0    # seconds between status polls
_SYBILION_MAX_POLLS      = 30     # 30 × 8 s = 4 min max wait

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "7200"))

STANDARDIZED_FACTORS: tuple[str, ...] = (
    "rent",
    "staff costs",
    "location foot traffic",
    "average basket price",
    "margin",
    "seasonality",
    "tourism dependency",
)

_FALLBACK_TEMPLATES: dict[str, str] = {
    "rent":                  "Average rent for a small retail location{loc}",
    "staff costs":           "Typical staff costs for a small retail business{loc}",
    "location foot traffic": "Monthly foot traffic{loc}",
    "average basket price":  "Average basket price per customer for {biz}",
    "margin":                "Typical gross margin for {biz}",
    "seasonality":           "Seasonal demand pattern for {biz} across the year",
    "tourism dependency":    "Tourism dependency of retail{loc}",
}

_DEMAND_TERMS: tuple[str, ...] = ("seasonality", "tourism", "weather", "demand", "revenue")

_STOPWORDS: frozenset[str] = frozenset({
    "average", "small", "retail", "location", "typical", "monthly", "business",
    "this", "that", "with", "from", "into", "over", "across", "year", "years",
    "their", "there", "type", "kind", "sort", "area", "customer", "customers",
    "based", "could", "affect", "success", "described", "across", "annual",
})


# ---------------------------------------------------------------------------
# Moral / legal gate — defined first so every function below can use it
# ---------------------------------------------------------------------------
class BusinessRejectedError(Exception):
    """Raised when the LLM gate determines the business idea is illegal or
    unethical. Carries a user-facing reason string."""
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_GATE_SYSTEM = (
    "You are a strict legal and ethics compliance officer for a business-analysis platform. "
    "Your ONLY job is to output a JSON object — never prose, never explanations.\n\n"
    "Set approved to false for ANY business that involves:\n"
    "  - Human body parts, organs, tissue, blood, or bodily fluids sold as products\n"
    "  - Illegal goods or services in the majority of jurisdictions: "
    "    unlicensed narcotics, weapons, counterfeit goods, stolen property\n"
    "  - Child exploitation, human trafficking, slavery\n"
    "  - Fraud, pyramid schemes, financial services designed to deceive\n"
    "  - Services whose PRIMARY purpose is to harm or kill people\n\n"
    "Set approved to true ONLY if the business is clearly "
    "legal and does not appear on the reject list above.\n\n"
    "When in doubt: reject.\n\n"
    "CRITICAL: output ONLY a JSON object. No explanations, no refusals, no prose."
)

_GATE_USER_TMPL = (
    "Evaluate this business for legal and ethical compliance.\n\n"
    "Business descriptions:\n{descriptions}\n\n"
    "Reply with a JSON object containing exactly two keys:\n"
    "  approved: boolean (true or false)\n"
    "  reason: string (explain why if false, empty string if true)\n"
    "Output only the JSON. No other text."
)

_STRICT_SUFFIX = (
    "\n\nIMPORTANT: your previous answer was not valid JSON. "
    "Return ONLY a single JSON object, no markdown fences, no commentary."
)


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------
@dataclass
class _Round:
    descriptions:    list[str]
    keywords:        list[str]
    statistic_title: str
    timeseries:      dict[str, float]
    de_raw:          dict[str, Any]


@dataclass
class _Session:
    session_id:           str
    initial_descriptions: list[str]            = field(default_factory=list)
    rounds:               list[_Round]         = field(default_factory=list)
    messages:             list[dict[str, str]] = field(default_factory=list)
    created_at:           float                = field(default_factory=time.time)
    last_used:            float                = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_used = time.time()

    def all_descriptions(self) -> list[str]:
        out = list(self.initial_descriptions)
        for r in self.rounds:
            out.extend(r.descriptions)
        return out

    def merged_timeseries(self) -> dict[str, float]:
        merged: dict[str, float] = {}
        for r in self.rounds:
            merged.update(r.timeseries)
        return merged

    def all_keywords(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for r in self.rounds:
            for kw in r.keywords:
                if kw not in seen:
                    seen.add(kw)
                    out.append(kw)
        return out

    def sybilion_payload(self) -> dict[str, Any]:
        ts    = self.merged_timeseries()
        title = self.rounds[-1].statistic_title if self.rounds else "Business revenue forecast"
        return {
            "pipeline_version": "v1",
            "frequency":        "monthly",
            "recency_factor":   0.6,
            "soft_horizon":     1,
            "timeseries_metadata": {
                "title":       title,
                "description": "; ".join(self.all_descriptions()),
                "keywords":    self.all_keywords(),
            },
            "timeseries": ts,
        }


_SESSION_STORE: dict[str, _Session] = {}


def _get_or_create_session(session_id: str | None) -> _Session:
    _purge_expired_sessions()
    if session_id and session_id in _SESSION_STORE:
        s = _SESSION_STORE[session_id]
        s.touch()
        return s
    new_id = session_id or str(uuid.uuid4())
    s = _Session(session_id=new_id)
    _SESSION_STORE[new_id] = s
    return s


def _purge_expired_sessions() -> None:
    now     = time.time()
    expired = [sid for sid, s in _SESSION_STORE.items()
               if now - s.last_used > SESSION_TTL_SECONDS]
    for sid in expired:
        del _SESSION_STORE[sid]


# ---------------------------------------------------------------------------
# Featherless LLM client
# ---------------------------------------------------------------------------
class FeatherlessClient:
    def __init__(
        self,
        api_key:  str | None = None,
        *,
        base_url: str | None = None,
        model:    str | None = None,
        timeout:  float = _LLM_TIMEOUT_S,
    ) -> None:
        self.api_key  = api_key or os.getenv("FEATHERLESS_API_KEY")
        self.base_url = (base_url or FEATHERLESS_BASE_URL).rstrip("/")
        self.model    = model or FEATHERLESS_MODEL
        self.timeout  = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 900) -> str:
        return self._call(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature, max_tokens=max_tokens,
        )

    def chat_with_history(
        self,
        messages:    list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens:  int   = 1400,
    ) -> str:
        return self._call(messages, temperature=temperature, max_tokens=max_tokens)

    def _call(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model":       self.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Sybilion client
# ---------------------------------------------------------------------------
class SybilionClient:
    def __init__(self, api_key: str | None = None, *, base_url: str | None = None) -> None:
        self.api_key  = api_key or os.getenv("SYBILION_API_KEY")
        self.base_url = (base_url or SYBILION_BASE_URL).rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def run_forecast(self, payload: dict[str, Any]) -> tuple[dict, dict]:
        with httpx.Client(timeout=_SYBILION_SUBMIT_TIMEOUT) as client:
            r = client.post(
                f"{self.base_url}/api/v1/forecasts",
                headers=self._headers(),
                json=payload,
            )
            r.raise_for_status()
            job_id = r.json()["job_id"]
            logger.info("Sybilion job submitted: %s", job_id)

            for attempt in range(_SYBILION_MAX_POLLS):
                time.sleep(_SYBILION_POLL_INTERVAL)
                status_r = client.get(
                    f"{self.base_url}/api/v1/forecasts/{job_id}",
                    headers=self._headers(),
                )
                status_r.raise_for_status()
                status_data = status_r.json()
                status = status_data.get("status", "")
                logger.info("Sybilion poll %d/%d — status: %s", attempt + 1, _SYBILION_MAX_POLLS, status)

                if status_data.get("settled") or status == "completed":
                    artifacts = {a["name"]: a["href"] for a in status_data.get("artifacts", [])}
                    forecast  = self._download_artifact(client, artifacts.get("forecast.json", ""))
                    signals   = self._download_artifact(client, artifacts.get("external_signals.json", ""))
                    return forecast, signals

                if status in ("failed", "canceled", "error"):
                    raise RuntimeError(f"Sybilion job {job_id} ended with status: {status}")

        raise RuntimeError(f"Sybilion job {job_id} did not complete within the polling window")

    def _download_artifact(self, client: httpx.Client, href: str) -> dict:
        if not href:
            return {}
        url = href if href.startswith("http") else f"{self.base_url}{href}"
        try:
            r = client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("Could not download Sybilion artifact %s: %s", href, exc)
            return {}


def _mock_sybilion_forecast() -> tuple[dict, dict]:
    from datetime import datetime, timedelta
    base   = datetime(2025, 4, 1)
    series = {}
    val    = 185.0
    for i in range(6):
        dt         = (base + timedelta(days=30 * i)).strftime("%Y-%m-%d")
        val       += 3.2 + (1.5 if i % 2 == 0 else -0.8)
        series[dt] = {
            "forecast": round(val, 2),
            "quantile_forecast": {
                "0.1": round(val * 0.88, 2),
                "0.5": round(val, 2),
                "0.9": round(val * 1.12, 2),
            },
        }
    forecast = {"_mock": True, "data": {"forecast_series": series}}
    signals  = {"_mock": True, "drivers": [
        {"name": "Consumer Price Index",    "importance": 0.81, "direction": "positive"},
        {"name": "Disposable Income Index", "importance": 0.73, "direction": "positive"},
        {"name": "Tourism Arrivals",        "importance": 0.57, "direction": "positive"},
        {"name": "Alcohol Excise Tax",      "importance": 0.44, "direction": "negative"},
    ]}
    return forecast, signals


# ---------------------------------------------------------------------------
# Timeseries cleaning
# ---------------------------------------------------------------------------
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_timeseries(raw: dict[str, Any]) -> dict[str, float]:
    candidate: dict | None = None
    for key in ("timeseries", "data", "time_series"):
        v = raw.get(key)
        if isinstance(v, dict):
            candidate = v
            break
    if candidate is None:
        candidate = raw

    cleaned: dict[str, float] = {}
    for k, v in candidate.items():
        if not isinstance(k, str) or not _DATE_RE.match(k):
            continue
        try:
            fval = float(v)
        except (TypeError, ValueError):
            continue
        normalised = k[:8] + "01"
        cleaned[normalised] = fval

    return dict(sorted(cleaned.items()))


# ---------------------------------------------------------------------------
# Strict-JSON parsing helpers
# ---------------------------------------------------------------------------
def _parse_json_object(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("empty LLM response")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        # No JSON found — check if the model returned refusal prose instead.
        # Surface it as BusinessRejectedError so the gate handles it correctly.
        lower = stripped.lower()
        if any(phrase in lower for phrase in (
            "cannot", "can't", "unable", "illegal", "not able",
            "i'm sorry", "i am sorry", "not appropriate", "not legal",
            "won't", "will not", "refuse", "not assist",
        )):
            first_sentence = re.split(r"[.\n]", stripped)[0].strip()
            raise BusinessRejectedError(
                first_sentence[:200] or "Request refused by compliance check."
            )
        raise ValueError("no JSON object in LLM response")
    return json.loads(stripped[start: end + 1])


def _coerce_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _llm_json(
    client: FeatherlessClient,
    system: str,
    user: str,
    stricter_user: str,
    *,
    max_tokens: int,
) -> dict:
    last_error: Exception | None = None
    for attempt, prompt in enumerate((user, stricter_user), start=1):
        try:
            return _parse_json_object(client.chat(system, prompt, max_tokens=max_tokens))
        except Exception as exc:
            last_error = exc
            logger.warning("Featherless attempt %d failed: %s", attempt, exc)
    raise last_error or RuntimeError("LLM call failed")


def _llm_json_with_history(
    client:     FeatherlessClient,
    messages:   list[dict[str, str]],
    *,
    max_tokens: int,
) -> tuple[dict, str]:
    last_error: Exception | None = None
    working = list(messages)
    raw     = ""

    for attempt in range(1, 3):
        try:
            raw    = client.chat_with_history(working, max_tokens=max_tokens)
            parsed = _parse_json_object(raw)
            return parsed, raw
        except Exception as exc:
            last_error = exc
            logger.warning("History LLM attempt %d failed: %s", attempt, exc)
            if attempt == 1:
                working.append({"role": "assistant", "content": raw})
                working.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Return ONLY a single JSON object with the exact keys requested. "
                        "No markdown fences, no prose."
                    ),
                })

    raise last_error or RuntimeError("Multi-turn LLM call failed")


# ---------------------------------------------------------------------------
# Gate implementation
# ---------------------------------------------------------------------------
def _check_moral_legal(
    descriptions: list[str],
    *,
    client: FeatherlessClient | None = None,
) -> None:
    """Run the moral/legal gate. Raises BusinessRejectedError if rejected.

    Passes silently when the LLM is unavailable — never block due to a missing key.
    """
    client = client or FeatherlessClient()
    if not client.available:
        logger.info("Gate LLM unavailable — skipping moral/legal check")
        return

    numbered    = "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions, 1))
    user_prompt = _GATE_USER_TMPL.format(descriptions=numbered)
    stricter    = user_prompt + _STRICT_SUFFIX

    try:
        data  = _llm_json(client, _GATE_SYSTEM, user_prompt, stricter, max_tokens=200)
        # Defensively strip stray quote characters from keys — some models return
        # the key as "approved" (with surrounding quotes) instead of approved.
        clean = {k.strip().strip("\"'"): v for k, v in data.items()}
        approved = bool(clean.get("approved", False))  # default False: ambiguous = reject
        reason   = str(clean.get("reason") or "").strip()
        if not approved:
            logger.warning("Business idea rejected by gate: %s", reason)
            raise BusinessRejectedError(reason or "This business concept cannot be analysed.")
    except BusinessRejectedError:
        raise
    except Exception as exc:
        # Any parse/network error → pass silently, don't block the pipeline
        logger.warning("Moral/legal gate check failed (%s); allowing through", exc)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------
_LOCATION_RE = re.compile(r"\bin\s+([A-Z][A-Za-z''.]+(?:\s+[\w''.]+){0,4})")
_BUSINESS_RE = re.compile(
    r"\b(?:open|start|launch|build|run|opening|starting|create|set\s+up)\s+"
    r"(?:an?\s+|my\s+|the\s+)?([a-z][\w'' -]*?)\s+(?:in|near|at|on)\b",
    re.IGNORECASE,
)


def _detect_location(text: str) -> str:
    m = _LOCATION_RE.search(text or "")
    return m.group(1).strip().rstrip(".") if m else ""


def _detect_business(text: str) -> str:
    m = _BUSINESS_RE.search(text or "")
    return m.group(1).strip().lower() if m else ""


def _fallback_descriptions(user_input: str) -> list[str]:
    location   = _detect_location(user_input)
    business   = _detect_business(user_input) or "this type of retail business"
    loc_suffix = f" in {location}" if location else ""
    return [_FALLBACK_TEMPLATES[f].format(loc=loc_suffix, biz=business) for f in STANDARDIZED_FACTORS]


def _derive_keywords(descriptions: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    for d in descriptions:
        for token in re.findall(r"[a-zA-Z]+", str(d).lower()):
            if len(token) > 3 and token not in _STOPWORDS:
                counts[token] += 1
    return [w for w, _ in counts.most_common()]


def _clamp_keywords(keywords: list[str], descriptions: list[str] | None = None) -> list[str]:
    cleaned: list[str] = []
    seen:    set[str]  = set()
    for kw in keywords:
        n = kw.strip().lower()
        if n and n not in seen:
            seen.add(n)
            cleaned.append(n)
    if len(cleaned) < 3:
        for candidate in (*_derive_keywords(descriptions or []), *_DEMAND_TERMS):
            if len(cleaned) >= 3:
                break
            if candidate not in seen:
                seen.add(candidate)
                cleaned.append(candidate)
    return cleaned[:6]


def _synthesize_title(descriptions: list[str], user_input: str | None = None) -> str:
    location = ""
    for c in ([user_input] if user_input else descriptions):
        location = _detect_location(c or "")
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

_C_SYSTEM = (
    "You are a senior business analyst for MarketPilot. "
    "You receive structured market data including Sybilion demand forecasts and external economic "
    "signals, and you produce a concise, data-driven business judgment. "
    "You ALWAYS return only strict JSON — no prose, no markdown fences. "
    "Each time new data arrives you update your judgment in light of ALL prior context in this "
    "session: every description, forecast series, signal, and previous judgment you have seen."
)


def _a_user(user_input: str) -> str:
    factors = "\n".join(f"{i}. {n}" for i, n in enumerate(STANDARDIZED_FACTORS, 1))
    return (
        f"Business idea: {user_input}\n\n"
        "Rephrase EACH of the following standardized factors into a concrete, searchable "
        "description tailored to this business and its location. Keep the same order.\n\n"
        f"Factors (in order):\n{factors}\n\n"
        'Return ONLY this JSON:\n'
        '{"descriptions": ["...", "...", "...", "...", "...", "...", "..."]}\n'
        f"The \"descriptions\" array must have at least {len(STANDARDIZED_FACTORS) + 5} items "
        "(one per factor, in order). You have to add 5 extra items for factors you consider "
        "important for this specific business."
    )


def _b_user(descriptions: list[str]) -> str:
    numbered = "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions, 1))
    return (
        "These are the confirmed factor descriptions for a business forecast:\n"
        f"{numbered}\n\n"
        "1. Extract 3-6 short keywords influential for these statistics. "
        "Prefer: product category, city, seasonality, tourism, weather.\n"
        "2. Write a concise statistic title for the core revenue series, e.g. "
        '"Average revenue of ice cream shops in Vienna".\n\n'
        'Return ONLY: {"keywords": ["...", "..."], "statistic_title": "..."}'
    )


def _c_user(session: _Session, new_descriptions: list[str], forecast: dict, signals: dict) -> str:
    all_desc = session.all_descriptions()
    ts       = session.merged_timeseries()
    keywords = session.all_keywords()
    round_n  = len(session.rounds)

    fc_series  = forecast.get("data", {}).get("forecast_series", forecast.get("forecast_series", {}))
    fc_summary = json.dumps(dict(list(sorted(fc_series.items()))[:12]), indent=2) if fc_series else "{}"
    drivers    = signals.get("drivers", signals.get("external_signals", []))[:6]
    drivers_txt = json.dumps(drivers, indent=2) if drivers else "[]"
    ts_recent  = dict(list(sorted(ts.items()))[-12:])
    new_block  = "\n".join(f"  - {d}" for d in new_descriptions)
    all_block  = "\n".join(f"  {i}. {d}" for i, d in enumerate(all_desc, 1))

    return (
        f"=== Round {round_n} ===\n\n"
        f"NEW descriptions added this round:\n{new_block}\n\n"
        f"ALL accumulated descriptions ({len(all_desc)} total):\n{all_block}\n\n"
        f"Keywords: {', '.join(keywords)}\n\n"
        f"Historical timeseries - last 12 observations:\n{json.dumps(ts_recent, indent=2)}\n"
        f"Total historical observations: {len(ts)}\n\n"
        f"Sybilion demand forecast:\n{fc_summary}\n\n"
        f"Top economic drivers (from Sybilion external_signals):\n{drivers_txt}\n\n"
        "Based on ALL of the above (including every prior judgment in this conversation), "
        "produce an updated business judgment. Return ONLY this JSON:\n"
        "{\n"
        '  "verdict": "go | no-go | adapt",\n'
        '  "score": <integer 1-10>,\n'
        '  "summary": "<2-3 sentence executive summary>",\n'
        '  "estimated_monthly_revenue_eur": <number>,\n'
        '  "estimated_monthly_costs_eur": <number>,\n'
        '  "estimated_monthly_profit_eur": <number>,\n'
        '  "payback_months": <integer>,\n'
        '  "strengths": ["...", "..."],\n'
        '  "risks": ["...", "..."],\n'
        '  "recommendation": "<one concrete action sentence>",\n'
        '  "changed_from_previous": "<what changed vs last judgment, or null on first round>"\n'
        "}"
    )


def _fallback_judgment(session: _Session) -> dict[str, Any]:
    ts  = session.merged_timeseries()
    avg = sum(ts.values()) / len(ts) if ts else 0
    return {
        "verdict":                       "adapt",
        "score":                         5,
        "summary":                       (
            f"Based on {len(session.all_descriptions())} descriptions and "
            f"{len(ts)} timeseries observations. LLM unavailable — deterministic fallback."
        ),
        "estimated_monthly_revenue_eur": round(avg * 1000),
        "estimated_monthly_costs_eur":   round(avg * 700),
        "estimated_monthly_profit_eur":  round(avg * 300),
        "payback_months":                24,
        "strengths":                     ["Market data collected"],
        "risks":                         ["LLM judgment unavailable"],
        "recommendation":                "Retry once the LLM service is available.",
        "changed_from_previous":         None,
    }


# ---------------------------------------------------------------------------
# Operation A — idea -> descriptions
# ---------------------------------------------------------------------------
def extract_descriptions(user_input: str, *, client: FeatherlessClient | None = None) -> list[str]:
    user_input = (user_input or "").strip()
    if not user_input:
        return _fallback_descriptions("")
    client = client or FeatherlessClient()
    # Gate checks the raw idea before the LLM generates any descriptions.
    # BusinessRejectedError propagates up to the HTTP route unchanged.
    _check_moral_legal([user_input], client=client)
    if client.available:
        try:
            data = _llm_json(client, _A_SYSTEM, _a_user(user_input),
                             _a_user(user_input) + _STRICT_SUFFIX, max_tokens=900)
            descriptions = _coerce_str_list(data.get("descriptions"))
            if len(descriptions) >= 3:
                return descriptions
        except Exception as exc:
            logger.warning("extract_descriptions LLM failed (%s); using fallback", exc)
    return _fallback_descriptions(user_input)


# ---------------------------------------------------------------------------
# Operation B helpers — descriptions -> keywords + title
# ---------------------------------------------------------------------------
def _keywords_and_title(
    descriptions: list[str],
    *,
    client: FeatherlessClient | None = None,
) -> tuple[list[str], str]:
    descriptions = _coerce_str_list(descriptions)
    if not descriptions:
        return _clamp_keywords([]), "Average revenue for the described business"
    client = client or FeatherlessClient()
    if client.available:
        try:
            data  = _llm_json(client, _B_SYSTEM, _b_user(descriptions),
                              _b_user(descriptions) + _STRICT_SUFFIX, max_tokens=300)
            kw    = _clamp_keywords(_coerce_str_list(data.get("keywords")), descriptions)
            title = str(data.get("statistic_title") or "").strip() or _synthesize_title(descriptions)
            if len(kw) >= 3:
                return kw, title
        except Exception as exc:
            logger.warning("keyword extraction LLM failed (%s); using fallback", exc)
    return _clamp_keywords(_derive_keywords(descriptions), descriptions), _synthesize_title(descriptions)


# ---------------------------------------------------------------------------
# Data-Engineer call
# ---------------------------------------------------------------------------
def call_data_engineer(description: str, key_word: list[str]) -> dict:
    payload  = {"description": description, "keyWord": list(key_word)}
    base_url = os.getenv("DATA_ENGINEER_URL")
    if base_url:
        try:
            with httpx.Client(timeout=_DATA_ENGINEER_TIMEOUT_S) as client:
                r = client.post(f"{base_url.rstrip('/')}/data/timeseries", json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            logger.warning("DE HTTP call failed (%s); falling back to in-process", exc)
    from backend.data_engineer import get_timeseries
    return get_timeseries(description, key_word)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------
def _run_pipeline(
    session:          _Session,
    new_descriptions: list[str],
    *,
    llm_client:       FeatherlessClient | None = None,
    sybilion_client:  SybilionClient    | None = None,
) -> dict[str, Any]:
    """Steps:
      0. LLM gate — reject illegal / unethical ideas immediately
      1. LLM — descriptions -> keywords + statistic title
      2. Data-Engineer — title + keywords -> raw timeseries
      3. Clean timeseries
      4. Record round on session
      5. Sybilion — merged timeseries -> forecast + signals
      6. LLM — judgment with full session context
      7. Return assembled response dict
    """
    llm_client      = llm_client      or FeatherlessClient()
    sybilion_client = sybilion_client or SybilionClient()

    # Step 0 — moral / legal gate (raises BusinessRejectedError if rejected)
    _check_moral_legal(new_descriptions, client=llm_client)

    # Step 1 — keywords + title
    keywords, title = _keywords_and_title(new_descriptions, client=llm_client)

    # Step 2 — Data-Engineer
    de_raw = call_data_engineer(title, keywords)

    # Step 3 — clean timeseries
    timeseries = _clean_timeseries(de_raw)
    logger.info("DE returned %d observations after cleaning", len(timeseries))

    # Step 4 — record round
    session.rounds.append(_Round(
        descriptions=new_descriptions,
        keywords=keywords,
        statistic_title=title,
        timeseries=timeseries,
        de_raw=de_raw,
    ))
    session.touch()

    # Step 5 — Sybilion
    sybilion_payload  = session.sybilion_payload()
    forecast, signals = _run_sybilion(sybilion_client, sybilion_payload)

    # Step 6 — LLM judgment
    judgment = _run_judgment(session, new_descriptions, forecast, signals, client=llm_client)

    # Step 7 — response (internal plumbing never leaves the server)
    return {
        "session_id":         session.session_id,
        "round":              len(session.rounds),
        "conversation_turns": max(0, (len(session.messages) - 1) // 2),
        "judgment":           judgment,
        "forecast_summary": {
            "statistic_title":  title,
            "keywords":         keywords,
            "observations":     len(session.merged_timeseries()),
            "forecast_horizon": sybilion_payload.get("soft_horizon"),
            "forecast_series": {
                dt: v["forecast"] if isinstance(v, dict) else v
                for dt, v in (
                    forecast.get("data", {})
                    .get("forecast_series", forecast.get("forecast_series", {}))
                    .items()
                )
            },
            "top_drivers": signals.get("drivers", signals.get("external_signals", []))[:5],
        },
    }


def _run_sybilion(client: SybilionClient, payload: dict[str, Any]) -> tuple[dict, dict]:
    if not client.available:
        logger.info("SYBILION_API_KEY not set; using mock forecast")
        return _mock_sybilion_forecast()
    try:
        return client.run_forecast(payload)
    except Exception as exc:
        logger.warning("Sybilion failed (%s); using mock forecast", exc)
        return _mock_sybilion_forecast()


def _run_judgment(
    session:          _Session,
    new_descriptions: list[str],
    forecast:         dict,
    signals:          dict,
    *,
    client:           FeatherlessClient | None = None,
) -> dict[str, Any]:
    client = client or FeatherlessClient()

    if not session.messages:
        session.messages.append({"role": "system", "content": _C_SYSTEM})

    user_msg = _c_user(session, new_descriptions, forecast, signals)
    session.messages.append({"role": "user", "content": user_msg})

    if client.available:
        try:
            parsed, raw = _llm_json_with_history(client, session.messages, max_tokens=1400)
            session.messages.append({"role": "assistant", "content": raw})
            return parsed
        except Exception as exc:
            logger.warning("Judgment LLM failed (%s); using fallback", exc)
            fallback = _fallback_judgment(session)
            session.messages.append({
                "role": "assistant",
                "content": json.dumps({**fallback, "_note": "fallback — LLM error"}),
            })
            return fallback
    else:
        fallback = _fallback_judgment(session)
        session.messages.append({
            "role": "assistant",
            "content": json.dumps({**fallback, "_note": "fallback — no API key"}),
        })
        return fallback


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------
def confirm_descriptions(
    descriptions:    list[str],
    *,
    llm_client:      FeatherlessClient | None = None,
    sybilion_client: SybilionClient    | None = None,
) -> dict[str, Any]:
    descriptions             = _coerce_str_list(descriptions)
    session                  = _get_or_create_session(None)
    session.initial_descriptions = descriptions
    return _run_pipeline(session, descriptions,
                         llm_client=llm_client, sybilion_client=sybilion_client)


def refine_with_descriptions(
    session_id:           str | None,
    new_descriptions:     list[str],
    *,
    initial_descriptions: list[str] | None    = None,
    llm_client:           FeatherlessClient | None = None,
    sybilion_client:      SybilionClient    | None = None,
) -> dict[str, Any]:
    new_descriptions = _coerce_str_list(new_descriptions)
    if not new_descriptions:
        raise ValueError("new_descriptions must be a non-empty list of strings")
    session = _get_or_create_session(session_id)
    if initial_descriptions and not session.initial_descriptions:
        session.initial_descriptions = _coerce_str_list(initial_descriptions)
    return _run_pipeline(session, new_descriptions,
                         llm_client=llm_client, sybilion_client=sybilion_client)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ExtractRequest(BaseModel):
    userInput: str = Field(..., min_length=1)

class ExtractResponse(BaseModel):
    descriptions: list[str]

class ConfirmRequest(BaseModel):
    descriptions: list[str] = Field(..., min_length=1)

class RefineRequest(BaseModel):
    sessionId:           str | None = Field(None)
    descriptions:        list[str]  = Field(..., min_length=1)
    initialDescriptions: list[str]  = Field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------
router = APIRouter(tags=["translation"])


@router.post("/api/extract", response_model=ExtractResponse)
def post_extract(request: ExtractRequest) -> JSONResponse:
    try:
        descriptions = extract_descriptions(request.userInput)
        return JSONResponse(content={"descriptions": descriptions})
    except BusinessRejectedError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "business_rejected", "reason": exc.reason})
    except Exception as exc:
        logger.exception("extract_descriptions failed")
        return JSONResponse(status_code=500,
                            content={"error": "translation_extract_failed", "detail": str(exc)})


@router.post("/api/confirm")
def post_confirm(request: ConfirmRequest) -> JSONResponse:
    try:
        result = confirm_descriptions(request.descriptions)
        return JSONResponse(content=result)
    except BusinessRejectedError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "business_rejected", "reason": exc.reason})
    except Exception as exc:
        logger.exception("confirm_descriptions failed")
        return JSONResponse(status_code=500,
                            content={"error": "translation_confirm_failed", "detail": str(exc)})


@router.post("/api/refine")
def post_refine(request: RefineRequest) -> JSONResponse:
    try:
        result = refine_with_descriptions(
            session_id=request.sessionId,
            new_descriptions=request.descriptions,
            initial_descriptions=request.initialDescriptions or None,
        )
        return JSONResponse(content=result)
    except BusinessRejectedError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "business_rejected", "reason": exc.reason})
    except ValueError as exc:
        return JSONResponse(status_code=422,
                            content={"error": "invalid_request", "detail": str(exc)})
    except Exception as exc:
        logger.exception("refine_with_descriptions failed")
        return JSONResponse(status_code=500,
                            content={"error": "translation_refine_failed", "detail": str(exc)})


@router.get("/api/session/{session_id}")
def get_session(session_id: str) -> JSONResponse:
    s = _SESSION_STORE.get(session_id)
    if not s:
        return JSONResponse(status_code=404, content={"error": "session_not_found"})
    return JSONResponse(content={
        "session_id":              s.session_id,
        "round":                   len(s.rounds),
        "all_descriptions":        s.all_descriptions(),
        "all_keywords":            s.all_keywords(),
        "timeseries_observations": len(s.merged_timeseries()),
        "conversation_turns":      max(0, (len(s.messages) - 1) // 2),
        "created_at":              s.created_at,
        "last_used":               s.last_used,
    })


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="MarketPilot — Translation Agent", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
         "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {
        "status":             "ok",
        "agent":              "translation",
        "version":            "3.1.0",
        "active_sessions":    len(_SESSION_STORE),
        "llm_available":      FeatherlessClient().available,
        "sybilion_available": SybilionClient().available,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

