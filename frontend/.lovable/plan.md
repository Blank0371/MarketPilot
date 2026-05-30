## MarketPilot — Implementation Plan

A polished, light-mode SaaS template for forecast-driven launch decisions. Static mock data, typed throughout, swappable for real APIs later.

### 1. Types — `src/lib/types.ts`

Define interfaces matching the spec exactly:
- `BusinessPitchInput` — `{ pitchText: string }`
- `Location` — `{ city; district; country }`
- `FinancialAssumptions` — investment, rent, staff, basket, margin, horizon
- `ConfidenceLevel` — `"High" | "Medium" | "Low"`
- `ExtractedAssumptions` — full structure from the spec (business_type, location, sales_channels, target_customers, pricing_position, business_model, forecast_target, forecast_keywords, confidence map, financial_assumptions)
- `ForecastPoint` — `{ month; p10; p50; p90 }`
- `DriverDirection` — `"positive" | "negative" | "mixed"`
- `Driver` — `{ name; importance; direction }`
- `ReasoningItem` — `{ factor; impact; explanation }`
- `Recommendation` — `"Launch" | "Adapt concept" | "Delay" | "Do not launch"`
- `AnalysisResult` — id, recommendation, break_even_probability, expected_monthly_profit, risk_score, downside_risk, forecast[], drivers[], reasoning[]
- `ScenarioChange` — `Partial<{ monthly_rent; average_basket_size; competition_level; gross_margin }>`
- `ScenarioResult` — previous/new recommendation+metrics, changed_metrics, reason_for_change

### 2. Mock data — `src/lib/mockData.ts`

Export the three JSON blobs from the spec verbatim, typed:
- `mockExtractedAssumptions: ExtractedAssumptions`
- `mockAnalysisResult: AnalysisResult`
- `mockScenarioResult: ScenarioResult`
- `exampleChips: string[]` (Wine shop in Vienna, Online delivery, …)
- `trustFeatures: string[]` (Probabilistic forecasts, Driver importance, …)
- `navLinks`, `heroCopy`, `stepLabels` so no copy lives inside components

### 3. Mock API — `src/lib/mockApi.ts`

Async functions with simulated latency (~700ms) and `// TODO: replace with fetch('/api/...')`:
- `extractAssumptions(pitchText: string): Promise<ExtractedAssumptions>`
- `analyzeBusiness(assumptions: ExtractedAssumptions): Promise<AnalysisResult>`
- `runScenario(base: AnalysisResult, changed: ScenarioChange): Promise<ScenarioResult>` — returns the spec's mock; if rent unchanged from 8000, return a softened variant so the UI still feels reactive

### 4. Routing & page shell

- Keep TanStack Start file-based routing. Single route `src/routes/index.tsx` renders `<Header />`, `<HeroSection />`, and the three-step workflow.
- Update route `head()` with MarketPilot title/description/og tags.
- Remove the placeholder image.

### 5. Design tokens — `src/styles.css`

Light-mode consulting palette in oklch:
- `--background` near-white, `--card` pure white, `--muted` soft gray
- `--primary` corporate blue (~oklch(0.55 0.18 250))
- Decision tokens: `--decision-launch` (green), `--decision-adapt` (amber), `--decision-delay` (orange), `--decision-danger` (red), each with `-foreground` and `-soft` (tinted background) variants
- Register all new tokens in `@theme inline` so Tailwind utilities like `bg-decision-adapt-soft` work
- Body font: Inter (system stack fallback); display: same with tight tracking. Add `@import` for Inter from Google Fonts in styles.css.

### 6. Components — `src/components/`

All receive data via props; no hard-coded business copy inside.

- **Header.tsx** — props: `{ navLinks; ctaLabel; onCta }`. Sticky, white, subtle border.
- **HeroSection.tsx** — props: `{ headline; slogan; subheadline; features: string[]; onStart }`. Compact trust row of pill chips.
- **Stepper.tsx** — props: `{ steps: {id; label}[]; current; onStepClick }`. Horizontal numbered stepper with connector lines; clickable to revisit.
- **PitchStep.tsx** — textarea, example chips (click fills textarea), submit button, loading state, helper text. Props: `{ examples; loading; onSubmit(text) }`.
- **ReviewAssumptionsStep.tsx** — renders an `ExtractedAssumptions` object as editable inputs/selects/chip rows; emits updated assumptions on change; "Run decision analysis" button. Props: `{ value; loading; onChange; onAnalyze }`.
  - Sub-elements: `ConfidenceBadge` (High=green, Medium=amber, Low=red), `ChipList` (add/remove).
- **DecisionAnalysisStep.tsx** — composes the dashboard: `<DecisionCard />`, two-column grid with `<ForecastChart />` + `<DriverImportanceChart />` on left, `<ReasoningPanel />` + `<ScenarioStressTest />` on right. Props: `{ analysis; baseAssumptions }`.
- **DecisionCard.tsx** — prominent recommendation banner + 4 `<MetricCard />`s. Color via `recommendation` → token mapping (`Launch→green`, `Adapt concept→amber`, `Delay→orange`, `Do not launch→red`).
- **MetricCard.tsx** — props: `{ label; value; sublabel?; tone? }`. Reused across decision + scenario before/after.
- **ForecastChart.tsx** — Recharts `LineChart` with three lines (p10 dashed gray, p50 solid blue, p90 dashed light blue). Props: `{ data: ForecastPoint[] }`.
- **DriverImportanceChart.tsx** — Recharts horizontal `BarChart` + direction badges legend. Props: `{ drivers: Driver[] }`.
- **ReasoningPanel.tsx** — list of reasoning items with impact badge. Props: `{ items: ReasoningItem[] }`.
- **ScenarioStressTest.tsx** — sliders (shadcn `Slider`) for rent, basket, competition, margin; on change calls `runScenario` and renders Before/After cards + reason. Props: `{ baseAnalysis; initialValues; onRun }`.

(Recharts is already an indirect dep via shadcn `chart.tsx`; verify and `bun add recharts` if needed.)

### 7. Page composition — `src/routes/index.tsx`

State machine:
```text
step: 1 | 2 | 3
pitchText, assumptions, analysis, scenarioResult, loading flags
```
- Step 1 → calls `extractAssumptions` → stores assumptions → advances to 2
- Step 2 → user edits → `analyzeBusiness` → stores analysis → advances to 3
- Step 3 → slider changes → `runScenario` → updates scenarioResult
- Stepper allows back-navigation; state persists across steps.
- Hero CTA scrolls to the workflow section.

### 8. Responsive

- Tailwind `md:` breakpoints. Dashboard grid `grid md:grid-cols-2 gap-6`.
- Stepper collapses to vertical numbers + label on `< md`.
- Header nav collapses to CTA-only on mobile (no hamburger needed for template).

### 9. Out of scope (per spec)

No auth, no DB, no maps, no chatbot, no backend, no Lovable Cloud.

### 10. Verification

- Build passes (auto-run by harness).
- Click-through: pitch → extract → review → analyze → adjust rent slider → see Before/After flip from "Adapt concept" to "Do not launch".
- Confirm decision color tokens render correctly.
