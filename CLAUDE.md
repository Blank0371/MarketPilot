# CLAUDE.md — Project Entry Point for Claude Code Agents

> **READ THIS FIRST, EVERY SESSION.** Before doing any work, read these files in
> order:
> 1. `CLAUDE.md` (this file) — what we build and how to behave
> 2. `ARCHITECTURE.md` — system wiring: blocks, the orchestrator, the HTTP flow, the report contract
> 3. `MODEL.md` — **the decision-model specification** (how the verdict and every number are computed)
> 4. `SYBILION_DOC.md` — the Sybilion forecasting API reference
> 5. Your assigned block file: `BLOCK1.md`, `BLOCK2.md`, `BLOCK3.md`, or `BLOCK4.md`
>
> Do not write code until you have read the relevant files for your block.
>
> **Source-of-truth order on conflicts:**
> - for **how the verdict/numbers are computed** → `MODEL.md` wins;
> - for **system wiring (routes, blocks, contracts)** → `ARCHITECTURE.md` wins;
> - then your `BLOCK*.md` file; then this file.
>
> Older `BLOCK*.md` / `FLOW_AND_AGENTS.md` notes describe a superseded design
> (async polling, "LLM writes & executes Python"). The current course is in
> `ARCHITECTURE.md` §9 and `MODEL.md`. If an old doc disagrees, the v2.0 docs win
> — flag the mismatch, do not reconcile silently.

---

## 1. Who we are and what we are building

We are a **4-person team** at the **Lumos Hackathon**, building for the
**Sybilion** challenge owner on the **Forecasting AI track**.

Sybilion provides a hosted **probabilistic forecasting API**. Our task is **not**
to train a forecasting model — Sybilion does that. We build a **decision agent /
application on top of** the API that turns a probabilistic forecast into a
concrete, transparent business decision.

**Product:** **MarketPilot** — *Navigate uncertainty before you launch.*

**Show case (the demo we present):** evaluating a business idea, specifically
**opening an ice cream shop in Vienna**, returning a data-driven investment
judgment. A user types a free-text idea; the system extracts the quantifiable
factors, fetches historical data, runs a Sybilion forecast, and returns a
dashboard with a revenue projection, investment estimate, drivers, graphs, and a
go / no-go verdict.

**The show case is the ice cream shop, but the system must be designed for ANY
retail (location-based) business.** Adding a new business should be a matter of
new inputs and values, not new code paths or a new model. Build generic; demo on
ice cream.

> Older documents may use a wine store as the example and/or the name
> "WineWise." The final name is **MarketPilot** and the demo is the **ice cream
> shop**. Read "wine store" / "WineWise" as superseded placeholders.

### 1.1 The current course (v2.0) — read this

The supervisor approved building a **smart LLM wrapper**. This shapes everything:

- **The LLM classifies and explains; deterministic Python computes.** An LLM
  profiler classifies the business onto axes (capital intensity, seasonality,
  etc.); deterministic code maps those categories to coefficients and computes
  every number and the verdict; an LLM phrases the reason over the finished
  numbers. The LLM **never** invents a number or the verdict. Full detail in
  `MODEL.md` (principles P1–P6).
- **The HTTP flow is synchronous.** The frontend makes **one call to
  `/api/analyze`** and gets the full report back. The old async polling design
  (`/api/confirm` → `job_id` → `/api/status` → `/api/result`) is **removed** —
  see `ARCHITECTURE.md` §9.
- **The priority criterion is accuracy / "not bullshit."** Because there is no
  ground truth (we forecast a business that does not exist), "accuracy" means
  internal consistency + forecast calibration (MAPE) + traceability (every number
  references a line in `MODEL.md`). This is what we defend to the jury.

---

## 2. The team and the four blocks

The system is split into four blocks, built in parallel against the contracts in
`ARCHITECTURE.md`. An **orchestrator** (`backend/main.py`) wires them into the
single synchronous `/api/analyze` endpoint.

| Block | Role |
|-------|------|
| **Block 1** | Frontend — idea input, results dashboard, **what-if controls** (change an assumption on stage → verdict updates) |
| **Block 2** | Data-Engineer agent — returns the historical monthly time series; an LLM profiler classifies the business and a deterministic generator shapes the series (mock for now) |
| **Block 3** | Translation agent — idea → descriptions, then descriptions → keywords (LLM on Featherless) |
| **Block 4** | Sybilion + report agent — Sybilion SDK forecast + the deterministic decision model (`MODEL.md`) → report JSON |

Read your own block file; skim `ARCHITECTURE.md` and `MODEL.md` so you understand
how your block connects to the others and where the numbers come from.

---

## 3. The factors our model accounts for

The translation agent works from a fixed set of **standardized factors**,
rephrasing each to fit the user's business. This is what makes the system
generalise — a new business reuses the same factors with new wording/values:

- **Rent** — everyone has it, often decisive.
- **Staff costs** — everyone.
- **Location foot traffic** — every location-based business.
- **Average basket price** — every retail business.
- **Margin** — everyone.
- **Seasonality** — everyone, but of varying strength (strong for ice cream).
- **Tourism dependency** — everyone in a tourist city.

For the ice cream show case, seasonality and tourism dependency are the decisive
factors.

In v2.0 the **decision model** additionally classifies the business onto a set of
**axes** (capital intensity at 5 levels, perishability, demand breadth, margin
class, ticket class, purchase frequency, external-shock sensitivity, seasonality
expectation). These axes drive the coefficient tables and the adaptive verdict
thresholds. See `MODEL.md` §3.2.

---

## 4. How to behave as an engineer (IMPORTANT)

**Act as a senior software developer with 20 years of experience.** Apply
professional best practices throughout:

- Clean, readable, well-named code. Clarity over cleverness.
- Small, single-purpose functions. Each block exposes **one clean interface**
  (endpoint/function) the others call — see the block files and `ARCHITECTURE.md`
  for exact shapes.
- Explicit error handling that honors the run mode (`MODEL.md` §1.1): in **`prod`**
  use the documented loud fallbacks (synthetic forecast, neutral profile, reason
  template) and record them in `runtime.fallbacks`; in **`dev`** raise an error
  instead of falling back silently. Never return a raw 500.
- Validate inputs at boundaries. Match the JSON contracts in `ARCHITECTURE.md`
  exactly — other blocks depend on them.
- **Every number you hard-code in the decision model must reference a section of
  `MODEL.md`** (a `# see MODEL.md §X.Y` comment). No reference → the number does
  not belong (principle P4).
- Don't over-engineer. This is a hackathon prototype. Build what the block file
  asks, make it work end-to-end, stop.
- Short, useful comments where logic is non-obvious.

---

## 5. Working rules for agents

1. **Write directly into `main`** — work in the real project files at their real
   module paths, not in a scratch/workbench area. No throwaway sandbox copies.
2. **Write basic tests.** For any module with real logic (data-engineer
   generator, Sybilion client, the report model), add 2–3 simple tests in
   `tests/` that confirm the core behaviour. Enough to catch breakage during
   integration and the live demo.
3. **Respect the contracts.** The JSON shapes in `ARCHITECTURE.md` §5 are fixed.
   If your output feeds another block, match the contract exactly. If you think a
   contract must change, flag it — don't silently diverge.
4. **Build the mock/fallback path from the start, but mode-aware.** The Sybilion
   forecast can be slow and the network can fail on stage. In `prod`, every block
   touching an external service works from cached/mock data and records the
   fallback in `runtime.fallbacks`. In `dev`, the same failure is an error so we
   see it (`MODEL.md` §1.1).
5. **Keep the show case working at all times.** The end-to-end demo ("ice cream
   shop Vienna" → dashboard) is the single most important deliverable. The
   synchronous `/api/analyze` path is the spine of the demo.
6. **The decision numbers are deterministic.** The LLM classifies (profiler) and
   explains (reason); deterministic Python computes revenue, costs, investment,
   break-even, and the verdict. Never let the LLM decide or invent a number
   (`MODEL.md` §0 P2).
7. **When in doubt, follow the source-of-truth order** (top of this file):
   `MODEL.md` for the model, `ARCHITECTURE.md` for the wiring, then your block
   file, then this file. Don't invent a third option to reconcile a conflict.
8. **Stack:** backend is **Python**; frontend is **TypeScript + React**.

---

## 6. The jury cares about three things

These drive design decisions:

1. **Does the forecast change the decision?** The recommendation must visibly
   depend on the forecast, not be generic. The verdict is multi-dimensional and
   the forecast (and its backtest) feeds confidence and break-even directly
   (`MODEL.md` §8.3, §6.5).
2. **Is the reasoning visible?** Driver importance, confidence bands, and the
   decision logic must be surfaced on the dashboard — not hidden in a chat
   output.
3. **Does the agent adapt when an assumption shifts mid-run?** When an input
   changes on stage, the result updates sensibly and transparently via
   `POST /report/recompute` (reuses the cached forecast, no Sybilion call). Treat
   the ability to change a key assumption and see the verdict update as a
   priority, not an afterthought.

**On the "plain LLM wrapper" rule:** the track originally forbade a plain wrapper
that pipes API output through a model and prints a summary. The supervisor
approved a **smart LLM wrapper** — and we honor the spirit of the original rule:
the numeric logic (revenue, costs, investment, decision) comes from
**deterministic Python that is actually executed**. The LLM is used to structure
input (descriptions/keywords), to classify the business (profiler), and to
explain results — never to invent the numbers or the verdict. The accuracy and
traceability of those numbers (`MODEL.md`) is exactly what we defend.
