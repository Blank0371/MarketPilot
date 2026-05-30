# FLOW_AND_AGENTS.md — Canonical Source of Truth

> **This file is the PRIMARY source of truth for the app flow, the agents, and
> the data contracts.** If anything in `CLAUDE.md`, `ARCHITECTURE.md`,
> `SYBILION_DOC.md`, or any block file disagrees with this document, **this
> document wins** and the other file should be corrected to match.
>
> Read order for any agent: `CLAUDE.md` → `ARCHITECTURE.md` → `SYBILION_DOC.md`
> → this file → your own block file.

---

## 1. Product

**MarketPilot** — *Navigate uncertainty before you launch.*

A forecasting-driven decision tool for future business owners. The user types a
business idea in free text. The system extracts the quantifiable factors that
affect the idea, lets the user confirm/edit them, fetches historical time series,
runs a probabilistic forecast via the Sybilion API, and returns a decision
report (revenue, costs, investment, drivers, graphs, go/no-go verdict + reason).

**Show case (demo):** an **ice cream shop in Vienna**. The system must remain
generic enough for any location-based retail business; ice cream is the demo, not
the limit.

---

## 2. End-to-end flow

```
Front-End            User types a free-text business idea
   │
   ▼
LLM (translation)    Filters the input into standardized, rephrased DESCRIPTIONS
   │                 of quantifiable factors
   ▼
Front-End            Shows the descriptions; user can add / delete / edit them
   │
   ▼
LLM (translation)    From the corrected descriptions, extracts 3–6 KEYWORDS
   │
   ▼
Data-Engineer        Receives {description, keyWord[]}; returns a historical
   │                 monthly time series + metadata
   ▼
Sybilion API layer   Builds the Sybilion request JSON from the time series +
   │                 metadata; submits forecast; fetches the 6-month prediction
   ▼
LLM (report)         Uses the prediction + user input + descriptions to write
   │                 and EXECUTE its own Python scripts: computes expected
   │                 revenue, graphs, investment cost, and a decision + reason
   ▼
Front-End            Renders the final report JSON
```

Step-by-step (the same flow, in words):

1. **Input (Front-End):** user enters a free-text idea.
2. **Filter (LLM):** extract a standardized description of the input.
3. **Confirm (Front-End):** return the filtered/standardized descriptions to the
   user; the user can delete or add their own.
4. **Keywords (LLM):** turn the corrected descriptions into keywords.
5. **Data (Data-Engineer):** from the description, look up the historical time
   series.
6. **Forecast (Sybilion layer):** send description + time series to the Sybilion
   API.
7. **Report (LLM):** take the prediction + the user input + all descriptions,
   then write a Python calculator that produces expected revenue + graphs +
   investment cost, and a decision.
8. **Result (LLM):** assemble a JSON for the frontend with: drivers, expected
   revenue, graphs, investment cost, decision (go / no-go / adapt concept) +
   reason.
9. **Display (Front-End):** render the JSON.

---

## 3. The standardized factors

The translation LLM works from a fixed set of standardized factors and rephrases
each one to fit the user's specific business. The factors are:

- **Rent**
- **Staff costs**
- **Location foot traffic**
- **Average basket price**
- **Margin**
- **Seasonality**
- **Tourism dependency**

Example of rephrasing: instead of the bare word "rent," the description becomes
*"Average rent for a small retail location in Vienna's 1st district."* Each
factor is reworded based on the `userInput`.

---

## 4. The agents and their contracts

There are three backend agents plus the frontend. Each backend agent is an
independent service with a POST REST endpoint. **All field names and JSON shapes
below are canonical — match them exactly.**

### 4.1 Translation agent (LLM input layer)

Two operations.

**(a) Idea → descriptions.** Receives the raw user input:
```json
{ "userInput": "Example long text describing the business idea…" }
```
Sends a request to an LLM hosted on **Featherless**, asking it to extract
descriptions of quantifiable factors that could affect the success of the
business. It injects the standardized factors (section 3) and rephrases each to
fit the `userInput`. Returns:
```json
{ "descriptions": ["Average rent for a small retail location in Vienna's 1st district…", "…"] }
```

**(b) Corrected descriptions → keywords.** Receives the user-corrected list back
from the frontend (descriptions added/removed):
```json
{ "descriptions": ["Average rent for a small retail location…", "…"] }
```
Extracts **3–6 keywords** from those descriptions — keywords that are (or
plausibly are) influential for the statistic the description will be used to
analyze. Then calls the Data-Engineer agent with:
```json
{
  "description": "Example description of a specific statistic",
  "keyWord": ["exampleKeyWord1", "exampleKeyWord2"]
}
```

### 4.2 Data-Engineer agent

Has a POST REST endpoint. Receives:
```json
{
  "description": "Average Revenue of Icecreamshops in Vienna with filter",
  "keyWord": ["exampleKeyWord1", "exampleKeyWord2"]
}
```

**For now it returns mock data** — realistic numbers for an ice cream shop. The
description will be something like *"Average Revenue of Icecreamshops in Vienna
with filter."* Returns:
```json
{
  "timeseries_metadata": {
    "title": "Average Revenue of Icecreamshops in Vienna with filter",
    "description": "Average Revenue of Icecreamshops in Vienna with filter.",
    "keywords": ["icecream", "restaurants", "weather", "seasons"]
  },
  "timeseries": {
    "2021-12-01": 218.5,
    "2022-01-01": 148.1,
    "2022-02-01": 145.9,
    "2022-03-01": 162.4,
    "2022-04-01": 168.7,
    "2022-05-01": 166.2
  }
}
```

**In the future** the agent finds the time series itself: it holds a set of
approved sources, each with a description and API schema. Based on the request it
picks the source it judges best, generates and executes an API request looking
for **monthly data for the last 5 years / 60 months**, and returns it in the same
standard JSON shape above.

### 4.3 Sybilion + report agent (LLM output layer)

Takes the Data-Engineer response and **transforms it into the Sybilion request
JSON**:
```json
{
  "pipeline_version": "v1",
  "frequency": "monthly",
  "soft_horizon": 6,
  "recency_factor": 0.5,
  "timeseries_metadata": {
    "title": "Average Revenue of Icecreamshops in Vienna with filter",
    "description": "Average Revenue of Icecreamshops in Vienna with filter.",
    "keywords": ["icecream", "restaurants", "weather", "seasons"]
  },
  "timeseries": {
    "2021-12-01": 218.5,
    "2022-01-01": 148.1,
    "2022-02-01": 145.9,
    "2022-03-01": 162.4,
    "2022-04-01": 168.7,
    "2022-05-01": 166.2
  }
}
```

Sends it to the Sybilion API **using Sybilion's Python SDK**. Fetches the result
artifact (the 6-month prediction). Then the LLM **decides which statistical tests
are needed** to generate the report, **writes its own Python scripts, and
executes them** to do so.

The report must contain: **expected revenue, graphs, investment cost, decision
(go / no-go / adapt concept) + reason.** This is sent back as the final JSON
response.

> Note on the "LLM writes math": the LLM orchestrates and writes the Python, but
> the **numbers come from deterministic Python that is actually executed**, not
> from the LLM guessing. The decision/verdict must be reproducible from the
> executed calculation, not invented by the model. This keeps us out of the
> "LLM-wrapper" failure mode the track forbids.

---

## 5. Final report JSON (Data-Engineer/report → Front-End)

The report agent returns a JSON the frontend renders. It contains at least:

- `drivers` — driver signals with importance and direction
- `expected_revenue` — expected monthly revenue (and supporting figures)
- `graphs` — the series to plot (forecast with confidence band, etc.)
- `investment_cost` — estimated investment (a breakdown is welcome)
- `decision` — go / no-go / adapt concept, with a quality indication
- `reason` — why this decision was made

The exact field layout is defined in `ARCHITECTURE.md` (kept consistent with this
flow). The frontend must not break if extra fields are present.

---

## 6. What changed vs older docs (so nobody is confused)

- **Two LLM steps before data**, not one: idea → *descriptions* (user edits) →
  *keywords*. Older docs had a single "idea → keywords" step.
- **The confirmation screen edits DESCRIPTIONS**, not raw keywords.
- **Three backend agents:** translation agent, data-engineer agent, Sybilion +
  report agent. Block numbering is mapped to these in `ARCHITECTURE.md`.
- **The report LLM writes and executes its own Python** for the statistics.
- Field names follow the JSON shapes in section 4 (`userInput`, `descriptions`,
  `description` + `keyWord`, the Data-Engineer/Sybilion shapes). Any older
  contract that conflicts is superseded.
