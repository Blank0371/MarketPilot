# MarketPilot Frontend Design Skill

## Purpose

Use this skill whenever improving the MarketPilot frontend UI.

MarketPilot is not a generic landing page and not a chatbot.

It is a premium forecasting-based decision cockpit for founders.

The UI must help the user understand:

* what the launch recommendation is
* why the recommendation was made
* what the financial outlook is
* how uncertain the forecast is
* which drivers matter most
* how changing assumptions changes the decision

## Visual Reference

Use the current screenshot style as the visual reference.

The design should feel like:

* premium dark SaaS
* founder cockpit
* forecasting intelligence
* financial clarity
* serious decision support
* high trust
* modern, but not playful

## Color System

Use a restrained dark cockpit palette.

Recommended tokens:

```css
--background-deep: #030712;
--background-navy: #07111f;
--background-elevated: #081827;

--surface-glass: rgba(15, 23, 42, 0.72);
--surface-glass-strong: rgba(15, 23, 42, 0.88);

--border-subtle: rgba(148, 163, 184, 0.14);
--border-active: rgba(34, 211, 238, 0.38);

--text-main: #f8fafc;
--text-secondary: #cbd5e1;
--text-muted: #94a3b8;

--accent-cyan: #22d3ee;
--accent-cyan-strong: #06b6d4;
--accent-violet: #8b5cf6;
--accent-indigo: #6366f1;

--success: #10b981;
--warning: #f59e0b;
--danger: #ef4444;
```

Use gradients sparingly:

* CTA: cyan to violet
* active step/card glow: low-opacity cyan
* page background: subtle navy/cyan radial glow

Avoid:

* white backgrounds
* pure black cards without borders
* random hex colors
* rainbow gradients
* heavy neon
* loud glowing effects
* excessive accent colors

## Typography

Use clear hierarchy.

Recommended scale:

* Hero headline: `text-5xl` to `text-7xl`
* Page heading: `text-4xl` to `text-5xl`
* Section heading: `text-2xl` to `text-3xl`
* Card heading: `text-lg` to `text-xl`
* Metric number: `text-3xl` to `text-5xl`
* Label: `text-xs uppercase tracking-wide`
* Body: `text-sm` to `text-base`

Rules:

* Metrics must be easy to scan.
* Section headings should be short and confident.
* Avoid long paragraphs in dashboard cards.
* Use muted explanatory copy below important labels.

## Layout

Use a strong cockpit layout:

* centered hero
* wide dashboard containers
* generous vertical spacing
* compact but readable cards
* responsive grids
* no cramped sections
* no decorative sections that do not support the demo

Spacing rhythm:

* section padding: `py-16`, `py-20`, or `py-24`
* card padding: `p-5`, `p-6`, or `p-8`
* grid gaps: `gap-4`, `gap-6`, or `gap-8`
* base spacing should follow an 8px rhythm

## Card System

Cards should use:

* dark glass background
* subtle border
* soft shadow
* optional low-opacity cyan glow for active/important states
* rounded corners
* strong title
* muted explanatory text
* clear content hierarchy

Avoid:

* flat gray blocks
* heavy borders
* overly bright backgrounds
* random card styles

## Button System

Primary CTA:

* cyan-to-violet gradient
* dark readable text or white text depending on contrast
* subtle glow
* rounded
* strong hover state

Secondary CTA:

* transparent or dark glass
* subtle border
* muted text
* brighter on hover

Avoid:

* too many primary buttons
* inconsistent button radii
* oversized hover scaling

## Animation Rules

Use Framer Motion only when it improves clarity.

Allowed:

* subtle page entrance fade
* single card reveal
* button hover polish
* metric/state transition
* Before vs After transition after assumption changes
* driver importance progress bar fill

Defaults:

```ts
const subtleMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.25, ease: "easeOut" },
};
```

Hover:

```ts
whileHover={{ y: -2 }}
transition={{ duration: 0.18, ease: "easeOut" }}
```

Do not use:

* bouncing
* spinning
* looping animation
* animated particles
* pulsing backgrounds
* heavy scroll-triggered animation
* large movement
* constant animated gradients

## Landing/Input Screen

The landing screen should communicate:

> Forecast first. Launch second.

Keep or use:

* headline: `Forecast first. Launch second.`
* subheadline: `Turn a raw business idea into editable market signals, probabilistic forecasts, financial projections, and a launch recommendation you can stress-test live.`
* primary CTA: `Analyze my idea`
* value chips:

  * Market signal extraction
  * Probabilistic forecasts
  * Financial projection
  * Live what-if sensitivity

The input section should feel like the first step of a decision cockpit, not a chatbot.

## Extracted Factor Screen

The backend shape is:

```json
{
  "descriptions": ["string"]
}
```

Rules:

* Render dynamically.
* Use editable market factor cards.
* Allow edit, delete, and add.
* Do not add new backend fields.
* Include helper text:
  `These factors will guide keyword generation and forecast retrieval.`
* Include an empty state.

## Result Dashboard

Use this exact section order:

1. Decision Recommendation
2. Financial Projection
3. Demand Forecast
4. What-if Sensitivity
5. Add another market factor
6. Before vs After
7. Driver Importance
8. Investment Breakdown
9. Reasoning & Recommended Moves

## Decision Recommendation

This is the anchor of the result dashboard.

It should show:

* decision label
* quality score
* risk level
* confidence
* summary
* recommended move

It should be visually stronger than other cards.

Use the first recommended action as the recommended move if available.

## Financial Projection

Show:

* expected monthly revenue
* expected monthly costs
* expected monthly profit
* estimated initial investment
* break-even probability
* payback period

Rules:

* Format EUR values clearly.
* Format percentages clearly.
* Make profit and break-even probability visually prominent.
* Include short explanatory copy.

## Demand Forecast

The forecast must look probabilistic.

Show:

* p10
* p50
* p90
* uncertainty range
* legend
* short interpretation

Explanation:

`The wider the band, the more uncertain the forecast. MarketPilot uses this uncertainty when forming the launch recommendation.`

## Forecast Reliability

Support optional `result.backtest`:

```json
{
  "mape": 0.118,
  "rmse": 94.2,
  "confidence_quality": "medium-high",
  "confidence_penalty": 0.06,
  "summary": "The model achieved 11.8% MAPE in historical backtests."
}
```

Show:

* MAPE as percentage
* RMSE if available
* confidence quality badge
* confidence penalty if available
* summary
* fallback state if missing

## What-if Sensitivity

Use exactly these six controls:

1. average_basket_size
2. gross_margin
3. staffing_level
4. opening_days_per_month
5. initial_investment_budget
6. product_price_level

Rules:

* No rent slider.
* Local recalculation only.
* No Sybilion call.
* Update Before vs After.
* Show changed assumptions.
* Label this as `Instant local recalculation`.

## Add Another Market Factor

This section is not the same as What-if Sensitivity.

Use:

* text input
* example: `Energy cost development for small retail stores in Vienna`
* label: `New forecast factor`
* helper text:
  `Unlike what-if assumptions, this asks the forecast pipeline to consider a new external driver.`

Use a mock function for now.

## Before vs After

This section proves adaptive behavior.

Show two cards:

Original result:

* decision
* break-even probability
* expected monthly revenue
* expected monthly profit
* risk level

Adjusted result:

* decision
* break-even probability
* expected monthly revenue
* expected monthly profit
* risk level

Below:

* changed assumptions
* added market factor if relevant
* impact summary

If nothing changed yet, show a premium empty state inviting the user to adjust What-if Sensitivity.

## Driver Importance

Render dynamically.

Show:

* name
* importance
* direction
* explanation

Use:

* progress bars
* positive/negative/neutral badges
* descending sort by importance if safe

## Investment Breakdown

Render dynamically.

Show:

* category
* amount
* total investment
* optional share visualization

Format all amounts in EUR.

## Reasoning & Recommended Moves

Use structured layout:

* Main reason
* Positive factors
* Negative factors
* Recommended moves

Avoid large walls of text.

Render all lists dynamically.

## Final Quality Bar

Before finishing, check:

* Does the UI feel like the screenshot?
* Is the decision obvious within 10 seconds?
* Is uncertainty visible?
* Is adaptivity obvious?
* Is the UI serious, premium, and not chatbot-like?
* Are arrays rendered dynamically?
* Is motion restrained?
* Are empty states handled?
* Does the build/typecheck pass?
