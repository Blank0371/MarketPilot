"""Connected data-source registry for the Data-Engineer agent.

This is the explicit, static list of sources the routing layer in
``data_engineer.py`` may select from. For this iteration every source is a
deterministic *mock* — one per supported retail-planning category — so the
pipeline keeps working with no external dependency and no credentials.

Real / proxy sources (e.g. the standalone ``data-engineer-agent`` Eurostat rent
index) can later be appended as entries with ``type`` set to ``"real"`` or
``"proxy"``; the routing layer already validates selections against this list,
so adding a source is data, not code.

The LLM resolver receives this list verbatim as routing context and must choose
``id`` values from it — it can never invent a source ID. See
``data_engineer.resolve_series``.
"""

from __future__ import annotations

# The mandatory retail-planning categories the agent must always answer for.
# Mirrors translation_agent.STANDARDIZED_FACTORS so a factor description always
# has a home.
SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "rent",
    "staff costs",
    "location foot traffic",
    "average basket price",
    "margin",
    "seasonality",
    "tourism dependency",
)

# Source-quality grades the resolver may assign, best -> worst.
SOURCE_QUALITIES: tuple[str, ...] = ("exact", "proxy", "mock", "none")

# Static registry. One deterministic mock source per mandatory category so the
# agent can always return *something* defensible. Keep entries JSON-serialisable
# — the dicts are passed verbatim to the LLM as routing context.
CONNECTED_SOURCES: list[dict] = [
    {"id": "mock_rent_retail", "name": "Deterministic mock retail rent profile",
     "categories": ["rent"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_city", "available": True},
    {"id": "mock_staff_costs", "name": "Deterministic mock staff cost profile",
     "categories": ["staff costs"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_city", "available": True},
    {"id": "mock_foot_traffic", "name": "Deterministic mock foot traffic profile",
     "categories": ["location foot traffic"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_retail_location", "available": True},
    {"id": "mock_average_basket_price", "name": "Deterministic mock average basket price profile",
     "categories": ["average basket price"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_market", "available": True},
    {"id": "mock_margin", "name": "Deterministic mock retail margin profile",
     "categories": ["margin"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_market", "available": True},
    {"id": "mock_seasonality", "name": "Deterministic mock seasonal demand index",
     "categories": ["seasonality"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_market", "available": True},
    {"id": "mock_tourism_dependency", "name": "Deterministic mock tourism dependency profile",
     "categories": ["tourism dependency"], "type": "mock", "granularity": "monthly",
     "geo_level": "generic_tourism_area", "available": True},
]


def is_supported_category(category: str | None) -> bool:
    """True iff ``category`` is one of the mandatory supported categories."""
    return isinstance(category, str) and category in SUPPORTED_CATEGORIES


def source_by_id(source_id: str | None) -> dict | None:
    """Return the registry entry with this id, or None if not connected."""
    if not source_id:
        return None
    for src in CONNECTED_SOURCES:
        if src["id"] == source_id:
            return src
    return None


def sources_for_category(category: str) -> list[dict]:
    """All registry entries that cover ``category``."""
    return [s for s in CONNECTED_SOURCES if category in s.get("categories", [])]


def default_source_for_category(category: str) -> dict | None:
    """First *available* source covering ``category`` (a mock source today)."""
    for src in sources_for_category(category):
        if src.get("available"):
            return src
    return None
