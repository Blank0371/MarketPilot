# BLOCK1.md — Frontend (Master Prompt for Claude Code)

> **Before you start, read in this order:** `CLAUDE.md` → `ARCHITECTURE.md` →
> `SYBILION_DOC.md` → `FLOW_AND_AGENTS.md` → this file. Then begin.
>
> **Source of truth:** `FLOW_AND_AGENTS.md` is canonical for flow and contracts.
> This block file is authoritative for frontend work. If they ever disagree,
> follow `FLOW_AND_AGENTS.md` and flag it. Ignore older docs that use a "wine
> store," the name "WineWise," or a `fields[]` field-array contract — superseded.
>
> **Product:** MarketPilot — *Navigate uncertainty before you launch.*
> **Show case:** ice cream shop in Vienna (UI stays generic for any retail).
> **Stack:** TypeScript + React.

---

## 0. Who you are

You are Claude, acting as a **world-class senior frontend engineer and product
designer with 20 years of experience** — someone who has shipped flagship
interfaces at **Red Bull, Louis Vuitton, Apple, ChatGPT (OpenAI), and Claude
(Anthropic)**. Combine Red Bull's high-energy, kinetic communication, Louis
Vuitton's luxury restraint, Apple's obsessive clarity and detail, and the calm
confidence of the best AI product cockpits.

You write **production-grade** code, apply best practices by default (clean
typed components, no dead code), and you sweat every detail: spacing, motion,
typography, contrast. No generic "AI slop." Every screen feels designed for
*this* product.

**Copywriting bar:** all UI copy — headlines, buttons, empty/loading states,
microcopy — must be **catchy and confident at Red Bull level**, while staying
credible for a serious decision tool. Punchy, not gimmicky. "Navigate
uncertainty before you launch," not "Welcome to our app." No vague startup
filler, no chatbot tone.

---

## 1. The task

**There is already a project in the `frontend/` folder. Refine and complete it —
do not start from zero.** First inspect what exists (structure, conventions,
components), then build on top: replace weak parts, lift the design to the bar
below, wire in the idea → confirm → results flow, and make everything work
end-to-end on mock data.

Work **directly in `frontend/` on the main code** (TypeScript + React), not in a
scratch copy. Keep existing build tooling unless it blocks the work.

---

## 2. The flow the UI must support

MarketPilot turns a free-text idea into a forecast-driven decision. The frontend
does **no** business logic — it collects input, lets the user confirm the
extracted assumptions, and visualizes the result.

Endpoints (see `ARCHITECTURE.md` §4–5 for exact shapes):

1. **Idea input** → `POST /api/extract` with `{ userInput }`.
2. Backend returns `{ descriptions: [...] }` — standardized, rephrased
   descriptions of the quantifiable factors affecting the business.
3. **Confirm step:** render the descriptions as an **editable list** — the user
   can **add, delete, and edit** them. (This is descriptions, not raw keywords.)
4. On confirm → `POST /api/confirm` with the edited `{ descriptions: [...] }` →
   backend returns `{ job_id }`.
5. **Poll** `GET /api/status/{job_id}` every ~3 s, showing the live pipeline step
   (`extracting` → `fetching` → `forecasting` → `reporting` → `done`).
6. When `done`, `GET /api/result/{job_id}` → the final report JSON.
7. **Results dashboard:** visualize the report.

**Hard rules:**
- No business math, forecasting, or financial logic in the frontend.
- Works **fully on mock data now**, structured so real API calls cleanly replace
  mocks later (clear `TODO` at each swap point).
- Must **not break if the backend returns extra/unknown fields** — render what it
  understands, ignore the rest.
- Show a **real polling loader** between confirm and results (the forecast is
  async). Use the step labels from `/api/status`; make the copy catchy, not a
  bare spinner.

---

## 3. Tech stack

- React + **TypeScript** (match what's in `frontend/`)
- Tailwind CSS
- Recharts (or the charting lib already present) for the forecast confidence band
- Component-based, reusable visual primitives

Support files to create/keep:
- `types.ts` — shared types (Descriptions payload, JobStatus, Report and its
  sub-objects: decision, expected_revenue, investment_cost, graphs, drivers,
  backtest, reason).
- `mockData.ts` — a realistic ice cream mock for each stage: a `descriptions`
  payload and a full report (matching `ARCHITECTURE.md` §5.6).
- `mockApi.ts` — mock `extract()`, `confirm()`, `getStatus()`, `getResult()` with
  `TODO` markers for the real `fetch` calls. `getStatus()` simulates the steps
  advancing to `done`.

---

## 4. Design direction

A **premium dark decision cockpit** — serious, elegant, high-contrast. Not a
chatbot, not a toy dashboard.

- Deep navy / near-black background; dark slate cards with depth (layered
  shadows, subtle borders, not flat boxes).
- **Electric blue / cyan** primary accent; **violet / indigo** secondary.
- Decision-state colors, used consistently wherever the verdict appears:
  **Emerald** = Launch, **Amber** = Adapt concept, **Orange** = Delay,
  **Red** = Do not launch.
- Distinctive, characterful typography — a strong display font paired with a
  clean body font. Avoid Inter / Roboto / Arial / system defaults.
- Atmosphere and depth: gradient meshes, subtle grain/noise, a glow on the
  primary accent. Avoid the cliché purple-on-white look.
- **Motion with intent:** one orchestrated load with staggered reveals; smooth
  transitions between steps; a satisfying moment when the verdict lands.

Match code complexity to the vision — refined means precise spacing and
restraint, not more effects for their own sake.

---

## 5. Screens & components

1. Header
2. Hero (carry the slogan; catchy, confident)
3. Stepper (Idea → Confirm → Results)
4. **Step 1 — Idea Input**
5. **Step 2 — Confirm Descriptions**
6. **Polling loader** (between confirm and results)
7. **Step 3 — Results Dashboard**
8. Verdict / Decision Card
9. Financial Metric Cards
10. Forecast Chart (history + forecast + confidence band)
11. Driver Importance section (with horizon if present)
12. Investment Breakdown section
13. Reason section (positive/negative factors + recommended actions)
14. Backtest quality badge

### Step 1 — Idea Input
Premium input card: large textarea; placeholder e.g. *"Example: I want to open a
premium ice cream shop in Vienna's 1st district focused on summer tourism and
seasonal specials."*; a few example-prompt chips; **Analyze idea** button;
loading state **"Reading your idea…"** (catchy).

### Step 2 — Confirm Descriptions
Render the backend's `descriptions` as an **editable list**. The user can edit
each line, delete lines, and add new ones. This is the user's chance to steer the
analysis — make it feel fast and important, with subtle helper copy explaining
that these factors drive the forecast. A **Confirm & forecast** button submits
the edited list.

### Polling loader
After confirm, show a loader that reflects the live pipeline step from
`GET /api/status/{job_id}` (`extracting` → `fetching` → `forecasting` →
`reporting` → `done`). Animated, catchy step copy. When `done`, fetch and show
results.

### Step 3 — Results Dashboard
Visualize the full report (`ARCHITECTURE.md` §5.6):
- **Verdict card** — big, color-coded by `decision.label`, with `score`,
  `risk_level`, `confidence`, and `summary`. This is the hero of the screen.
- **Financial cards** — expected monthly revenue / costs / profit, break-even
  probability, payback months; optionally downside vs upside profit.
- **Forecast chart** — plot `graphs.historical_series` + `graphs.demand_forecast`
  as one timeline: solid historical line, forecast continuation, shaded
  `low`–`high` confidence band.
- **Drivers** — horizontal importance bars; color/sort by `direction`
  (positive vs negative). If `horizon` is present, show how importance shifts
  (e.g. month 1 vs month 6).
- **Investment** — the breakdown list and total.
- **Reason** — positive factors, negative factors, recommended actions.
- **Backtest badge** — small "forecast quality: medium-high · MAPE 12%" element
  so the reasoning is grounded and visible.

---

## 6. Adaptivity (important — do not skip)

The jury changes an assumption live and expects the result to update. Give the
dashboard a lightweight way to re-run with a tweaked assumption **without a new
forecast** (the forecast stays cached; only the economics recompute).

Provide a small **"What-if" control** on the results screen: 1–3 inputs/sliders
for the most decision-relevant assumptions (e.g. monthly rent, average basket
price, margin). On change, call a recompute path and **visibly update the verdict
and financials** (animate the change). For the frontend mock, implement this as a
local `recompute(report, overrides)` in `mockApi.ts` that adjusts revenue/costs
and re-derives the verdict label, with a `TODO` to point it at the backend's fast
recompute endpoint later.

This is what demonstrates "the agent adapts mid-run" — one of the three live-demo
dimensions. Keep it elegant and obviously responsive.

---

## 7. Definition of done

- End-to-end on **mock data**, no console errors: idea → confirm descriptions →
  polling loader → results dashboard.
- Descriptions render as an **editable list** (add/edit/delete); polling loader
  advances through the steps to `done`; extra unknown fields don't crash the UI.
- Dashboard renders every part of the report contract: verdict (color-coded),
  financial cards, forecast chart with history + forecast + confidence band,
  driver bars, investment breakdown, reason, backtest badge.
- **What-if control** re-runs locally and visibly changes the verdict.
- `types.ts`, `mockData.ts`, `mockApi.ts` exist with `TODO` markers for
  `/api/extract`, `/api/confirm`, `/api/status`, `/api/result`, and the recompute
  path.
- Hits the design bar: premium dark cockpit, distinctive type, intentional
  motion, catchy Red Bull-level copy throughout.
- Clean, typed, component-based; builds on the existing `frontend/` project.

---

## 8. Reminders

- Backend wiring happens at integration. Until then everything runs on
  `mockApi.ts`; structure each swap as a one-line change.
- Keep contract field names **exactly** as in `ARCHITECTURE.md` §5 — Blocks 2–4
  produce these.
- If this file conflicts with reality in `frontend/`, prefer the contract shapes
  here and leave a `TODO`. If it conflicts with another doc, follow
  `FLOW_AND_AGENTS.md`.
