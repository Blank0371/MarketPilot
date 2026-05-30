# MarketPilot Claude Code Instructions

Work only inside the `frontend` folder.

Do not edit backend files.

## Product

MarketPilot is a forecasting-based decision intelligence app for future business owners and entrepreneurs.

It turns a raw business idea into:

* editable market factor descriptions
* forecast keywords
* historical time-series data
* probabilistic forecasts
* financial projections
* investment estimates
* driver importance
* a clear decision recommendation
* founder-controllable what-if sensitivity
* before/after comparison

Core promise:

> MarketPilot does not only forecast the market. It shows how a founder can adapt a business concept until it becomes viable.

## Visual Direction

The current screenshot is the visual reference.

Preserve and extend this style:

* dark premium SaaS
* decision cockpit feeling
* near-black navy background
* subtle cyan glow
* cyan-to-violet CTA gradient
* dark glass cards
* thin slate borders
* cool muted text
* restrained premium look
* no chatbot UI
* no generic AI dashboard aesthetic

Use the existing visual mood, but make it more consistent across the whole app.

## Color Scheme

Use this palette direction:

* Background: near-black navy / deep charcoal
* Surface: dark slate / navy glass
* Primary accent: cyan
* Secondary accent: violet
* Success: emerald
* Warning: amber
* Danger: red
* Text: cool white and slate-muted text

Avoid:

* white backgrounds
* rainbow gradients
* excessive neon
* playful colors
* heavy animated gradients
* too many accent colors

## Animation Rules

Use Framer Motion sparingly.

Animation should support clarity, not decoration.

Allowed:

* one subtle page entrance fade
* small card entrance opacity transition
* soft hover transition on buttons/cards
* smooth metric value/state transition
* Before vs After transition when assumptions change
* progress bar fill animation for driver importance

Avoid:

* excessive scroll animations
* bouncing
* spinning
* pulsing backgrounds
* repeated stagger animations on every section
* animated particles
* animated gradients that constantly move
* anything that distracts from decision-making

Motion defaults:

* duration: 0.15s to 0.35s
* easing: easeOut
* y-offset: 8px to 12px maximum
* opacity from 0 to 1
* no spring bounce unless extremely subtle

## Main Demo Story

The frontend must support this demo flow:

1. User enters a business idea.
2. MarketPilot extracts editable business factors.
3. User edits, deletes, or adds factors.
4. Forecast dashboard shows decision, financials, forecast uncertainty, drivers, investment, and reasoning.
5. User changes founder-controllable what-if assumptions.
6. Before/After comparison shows how the recommendation changes.
7. User can add another market factor for future forecast refinement.

## Backend Extraction Contract

The MVP backend returns:

```json
{
  "descriptions": [
    "Average monthly rent for a 100-200 sqm retail space in Vienna's 1st district",
    "Average basket price for wine purchases in Vienna's high-end retail stores",
    "Average gross profit margin for wine retailers in Vienna"
  ]
}
```

Frontend rules:

* Render descriptions dynamically with `descriptions.map(...)`.
* Do not assume a fixed number of descriptions.
* User can delete a description by removing it from the array.
* User can add a description by appending to the array.
* Do not add `analysis_id`, `category`, or `selected` fields for the MVP.

## Result Dashboard Order

Use this exact order:

1. Decision Recommendation
2. Financial Projection
3. Demand Forecast
4. What-if Sensitivity
5. Add another market factor
6. Before vs After
7. Driver Importance
8. Investment Breakdown
9. Reasoning & Recommended Moves

## What-if Sensitivity

Use exactly these six founder-controllable overrides:

1. Average basket size
2. Gross margin
3. Staffing level
4. Opening days per month
5. Initial investment budget
6. Product price level

Rules:

* No rent slider.
* What-if sensitivity must not call Sybilion.
* It only recalculates local/mock business assumptions.
* It should update the Before vs After comparison immediately.
* Make this section feel interactive but serious.

## Add Another Market Factor

This is different from What-if Sensitivity.

What-if Sensitivity:

* instant local recalculation
* founder-controllable assumptions
* no Sybilion call

Add another market factor:

* new external market factor
* future backend/Sybilion forecast pipeline
* mock function for now

Make this distinction visually clear.

## Component Direction

Prefer modular components:

* DecisionRecommendation
* FinancialProjection
* DemandForecast
* ForecastReliability
* WhatIfSensitivity
* AddMarketFactor
* BeforeAfterComparison
* DriverImportance
* InvestmentBreakdown
* ReasoningPanel
* MetricCard
* StatusBadge
* GlassCard
* SectionShell

## Validation

After edits:

1. Inspect `package.json`.
2. Run the safest available validation command.
3. Prefer `npm run build`, `npm run lint`, or `npm run typecheck` if available.
4. Fix frontend-only errors.
5. Confirm no backend files were changed.
6. Summarize changed files and remaining risks.
