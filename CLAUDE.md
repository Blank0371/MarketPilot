# CLAUDE.md — Project Entry Point for Claude Code Agents

> **READ THIS FIRST, EVERY SESSION.** Before doing any work, read these files in
> order:
> 1. `CLAUDE.md` (this file) — what we build and how to behave
> 2. `ARCHITECTURE.md` — system architecture, blocks, and result contract
> 3. `SYBILION_DOC.md` — the Sybilion forecasting API reference
> 4. `FLOW_AND_AGENTS.md` — **the canonical source of truth** for the flow,
>    agents, and JSON contracts
> 5. Your assigned block file: `BLOCK1.md`, `BLOCK2.md`, `BLOCK3.md`, or
>    `BLOCK4.md`
>
> Do not write code until you have read all of these for your block.
>
> **Source-of-truth order on conflicts:** `FLOW_AND_AGENTS.md` wins over
> everything; then your `BLOCK*.md` file; then `ARCHITECTURE.md`; then this file.
> If two docs disagree, follow that order and flag the mismatch.

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
judgment. A user types a free-text idea; the system extracts and confirms the
quantifiable factors, fetches historical data, runs a Sybilion forecast, and
returns a dashboard with a revenue projection, investment estimate, drivers,
graphs, and a go / no-go verdict.

**The show case is the ice cream shop, but the system must be designed for ANY
retail (location-based) business.** Adding a new business should be a matter of
new inputs and values, not new code paths or a new model. Build generic; demo on
ice cream.

> Older documents may use a wine store as the example and/or the name
> "WineWise." The final name is **MarketPilot** and the demo is the **ice cream
> shop**. Read "wine store" / "WineWise" as superseded placeholders.

---

## 2. The team and the four blocks

The system is split into four blocks, built in parallel against the contracts in
`FLOW_AND_AGENTS.md`. Each block is given to a separate Claude Code agent.

| Block | Role (see `FLOW_AND_AGENTS.md` §4) |
|-------|-------------------------------------|
| **Block 1** | Frontend — idea input, description confirmation, results dashboard |
| **Block 2** | Data-Engineer agent — returns historical monthly time series (mock for now) |
| **Block 3** | Translation agent — idea → descriptions, then descriptions → keywords (LLM on Featherless) |
| **Block 4** | Sybilion + report agent — Sybilion SDK forecast, then LLM writes & executes Python to build the report |

Read your own block file in detail; skim `ARCHITECTURE.md` and
`FLOW_AND_AGENTS.md` so you understand how your block connects to the others.

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

---

## 4. How to behave as an engineer (IMPORTANT)

**Act as a senior software developer with 20 years of experience.** Apply
professional best practices throughout:

- Clean, readable, well-named code. Clarity over cleverness.
- Small, single-purpose functions. Each block exposes **one clean interface**
  (endpoint/function) the others call — see the block files for exact shapes.
- Explicit error handling. Never return a raw 500. Use the fallbacks in
  `ARCHITECTURE.md` (mock data on API failure, retries on malformed LLM output,
  partial results when something is missing).
- Validate inputs at boundaries. Match the JSON contracts in
  `FLOW_AND_AGENTS.md` exactly — other blocks depend on them.
- Don't over-engineer. This is a hackathon prototype. Build what the block file
  asks, make it work end-to-end, stop.
- Short, useful comments where logic is non-obvious.

---

## 5. Working rules for agents

1. **Write directly into `main`** — work in the real project files at their real
   module paths, not in a scratch/workbench area. No throwaway sandbox copies.
2. **Write basic tests.** For any module with real logic (data-engineer mock,
   Sybilion client, the calculator/report), add 2–3 simple tests in `tests/` that
   confirm the core behaviour. Not exhaustive — enough to catch breakage during
   integration and the live demo.
3. **Respect the contracts.** The JSON shapes in `FLOW_AND_AGENTS.md` are fixed.
   If your output feeds another block, match the contract exactly. If you think a
   contract must change, flag it — don't silently diverge.
4. **Build a mock/fallback path from the start.** The Sybilion forecast endpoint
   is asynchronous and can take minutes; the network can fail on stage. Every
   block touching an external service must work from cached/mock data when the
   real service is unavailable.
5. **Keep the show case working at all times.** The end-to-end demo ("ice cream
   shop Vienna" → dashboard) is the single most important deliverable.
6. **When in doubt, follow the source-of-truth order** (top of this file):
   `FLOW_AND_AGENTS.md`, then your block file, then `ARCHITECTURE.md`, then this
   file. Don't invent a third option to reconcile a conflict.
7. **Stack:** backend is **Python**; frontend is **TypeScript + React**.

---

## 6. The jury cares about three things

These drive design decisions:

1. **Does the forecast change the decision?** The recommendation must visibly
   depend on the forecast, not be generic.
2. **Is the reasoning visible?** Driver importance, confidence bands, and the
   decision logic must be surfaced on the dashboard — not hidden in a chat
   output.
3. **Does the agent adapt when an assumption shifts mid-run?** When an input
   changes on stage, the result should update sensibly and transparently. This is
   one of the three live-demo dimensions — treat the ability to change a key
   assumption and see the verdict update as a priority, not an afterthought.

Hard rule from the track: a **plain LLM wrapper that pipes API output through a
model and prints a summary is not acceptable.** The numeric logic (revenue,
costs, investment, decision) comes from **deterministic Python that is actually
executed**. The LLM is used to structure input (descriptions/keywords), to
orchestrate and write that Python, and to explain results — never to invent the
numbers or the verdict.
