import { ECONOMICS } from "./mockData";
import { pickMockCaseId, getMockCase, DEFAULT_MOCK_CASE_ID } from "./mockCases";
import type {
  DescriptionsPayload,
  ConfirmResponse,
  JobStatus,
  PipelineStep,
  Report,
  OverridesMap,
  ComparisonResult,
  ComparisonSummary,
  ChangedAssumption,
  AddMarketFactorResult,
  AddedMarketFactor,
} from "./types";

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

const jobRegistry = new Map<string, number>();

// Which show-case the demo is currently running. `extract` selects it from the
// idea text; `getResult` returns that case's report. Module-level state is fine
// for the sequential single-user demo flow (idea → confirm → results).
let selectedCaseId = DEFAULT_MOCK_CASE_ID;

// ─── Extract ─────────────────────────────────────────────────────────────────

/**
 * TODO: Replace with real call:
 *   fetch('/api/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ userInput }) }).then(r => r.json()) as Promise<DescriptionsPayload>
 */
export async function extract(userInput: string): Promise<DescriptionsPayload> {
  await delay(1100);
  // Pick the show-case from the idea text and remember it for getResult.
  selectedCaseId = pickMockCaseId(userInput);
  return { descriptions: [...getMockCase(selectedCaseId).descriptions] };
}

// ─── Confirm ──────────────────────────────────────────────────────────────────

/**
 * TODO: Replace with real call:
 *   fetch('/api/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ descriptions }) }).then(r => r.json()) as Promise<ConfirmResponse>
 */
export async function confirm(descriptions: string[]): Promise<ConfirmResponse> {
  await delay(350);
  void descriptions;
  const job_id = `job_${Date.now()}`;
  jobRegistry.set(job_id, Date.now());
  return { job_id };
}

// ─── Status polling ───────────────────────────────────────────────────────────

const STEP_SCHEDULE: Array<{ after_ms: number; step: PipelineStep }> = [
  { after_ms: 0, step: "extracting" },
  { after_ms: 2800, step: "fetching" },
  { after_ms: 5600, step: "forecasting" },
  { after_ms: 8800, step: "reporting" },
  { after_ms: 11500, step: "done" },
];

/**
 * TODO: Replace with real call:
 *   fetch(`/api/status/${job_id}`).then(r => r.json()) as Promise<JobStatus>
 */
export async function getStatus(job_id: string): Promise<JobStatus> {
  await delay(300);
  const startedAt = jobRegistry.get(job_id) ?? Date.now();
  const elapsed = Date.now() - startedAt;
  let step: PipelineStep = "extracting";
  for (const s of STEP_SCHEDULE) {
    if (elapsed >= s.after_ms) step = s.step;
  }
  return { job_id, step, done: step === "done" };
}

// ─── Result ───────────────────────────────────────────────────────────────────

/**
 * TODO: Replace with real call:
 *   fetch(`/api/result/${job_id}`).then(r => r.json()) as Promise<Report>
 */
export async function getResult(job_id: string): Promise<Report> {
  await delay(200);
  void job_id;
  // Return the show-case selected by `extract` (deep-cloned so downstream
  // what-if / add-factor never mutate the shared dataset).
  return structuredClone(getMockCase(selectedCaseId).report);
}

// ─── What-if recalculation ────────────────────────────────────────────────────

/**
 * How demand multiplier changes by product_price_level.
 * Higher price = fewer customers; lower price = more customers.
 */
const DEMAND_MULT: Record<string, number> = {
  budget: 1.25,
  "mid-market": 1.05,
  premium: 1.0,
  luxury: 0.7,
};

/**
 * Recalculate business metrics client-side from adjusted assumptions.
 * Does NOT call Sybilion — the forecast stays fixed; only economics change.
 *
 * TODO: Wire to a fast backend recompute endpoint:
 *   fetch('/api/recompute', { method: 'POST',
 *     body: JSON.stringify({ base_report_id, overrides }) }).then(r => r.json())
 * TODO: Add debouncing (e.g. 300ms) before calling the real backend to avoid
 *       excessive requests during slider drags.
 */
export async function mockRecalculateWithOverrides(
  baseReport: Report,
  overrides: OverridesMap,
): Promise<ComparisonResult> {
  await delay(120); // simulate slight async

  // ── Base values (defaults) ─────────────────────────────────────────────────
  const BASE_BASKET = ECONOMICS.base_basket_size; // 42 EUR
  const BASE_DAYS = ECONOMICS.base_opening_days; // 22 days
  const BASE_MARGIN = 0.35;
  const BASE_STAFF = 1; // employees

  // ── Read overrides ────────────────────────────────────────────────────────
  const basket = (overrides["average_basket_size"] as number) ?? BASE_BASKET;
  const margin = (overrides["gross_margin"] as number) ?? BASE_MARGIN;
  const staffing = (overrides["staffing_level"] as number) ?? BASE_STAFF;
  const days = (overrides["opening_days_per_month"] as number) ?? BASE_DAYS;
  const investment = (overrides["initial_investment_budget"] as number) ?? 120000;
  const price_level = (overrides["product_price_level"] as string) ?? "premium";

  const demand_mult = DEMAND_MULT[price_level] ?? 1.0;

  // ── Anchor to baseReport so values match exactly when sliders are at defaults
  //
  //   Revenue scales proportionally:
  //     new_revenue = base_revenue × (basket/BASE_BASKET) × (days/BASE_DAYS) × demand_mult
  //   This guarantees: at base values → new_revenue == baseReport.financials.expected_monthly_revenue
  //
  //   Costs delta:
  //     COGS change = new_revenue×(1−margin) − base_revenue×(1−BASE_MARGIN)
  //     Staff change = (staffing − BASE_STAFF) × staff_cost_per_employee
  //     Fixed overhead unchanged
  //   This guarantees: at base values → new_costs == baseReport.financials.expected_monthly_costs
  // ─────────────────────────────────────────────────────────────────────────
  const base_revenue = baseReport.financials.expected_monthly_revenue;
  const base_costs = baseReport.financials.expected_monthly_costs;

  const revenue_scale = (basket / BASE_BASKET) * (days / BASE_DAYS) * demand_mult;
  const new_revenue = Math.round(base_revenue * revenue_scale);

  const cogs_delta = new_revenue * (1 - margin) - base_revenue * (1 - BASE_MARGIN);
  const staff_delta = (staffing - BASE_STAFF) * ECONOMICS.staff_cost_per_employee;
  const new_costs = Math.round(base_costs + cogs_delta + staff_delta);

  const new_profit = new_revenue - new_costs;
  const profit_margin = new_revenue > 0 ? new_profit / new_revenue : -1;

  // ── Verdict, BEP, Risk — all anchored to baseReport ──────────────────────
  //
  //   BEP: shift from base_bep proportional to the profit-margin change.
  //     At base values → delta = 0 → new_bep == base_bep exactly.
  //
  //   Risk: derived from new_bep so the two stay consistent with each other.
  //     At base values → new_bep == base_bep → same risk band as baseReport.
  // ─────────────────────────────────────────────────────────────────────────
  const base_profit = baseReport.financials.expected_monthly_profit;
  const base_bep = baseReport.financials.break_even_probability;
  const base_margin = base_revenue > 0 ? base_profit / base_revenue : 0;

  const margin_delta = profit_margin - base_margin;
  const new_bep = Math.max(0.05, Math.min(0.97, base_bep + margin_delta * 2.5));
  const new_risk = deriveRiskFromBep(new_bep);
  const new_decision = deriveVerdict(profit_margin);
  const payback = new_profit > 0 ? Math.round(investment / new_profit) : 999;
  void payback;

  // ── Changed assumptions ───────────────────────────────────────────────────
  const changes: ChangedAssumption[] = [];
  if (Math.abs(basket - BASE_BASKET) > 0.01)
    changes.push({ label: "Average basket size", old: BASE_BASKET, new: basket, unit: "EUR" });
  if (Math.abs(margin - BASE_MARGIN) > 0.001)
    changes.push({ label: "Gross margin", old: BASE_MARGIN, new: margin, unit: "%" });
  if (staffing !== BASE_STAFF)
    changes.push({ label: "Staffing level", old: BASE_STAFF, new: staffing, unit: "employees" });
  if (days !== BASE_DAYS)
    changes.push({ label: "Opening days per month", old: BASE_DAYS, new: days, unit: "days" });
  if (Math.abs(investment - 120000) > 1)
    changes.push({ label: "Initial investment budget", old: 120000, new: investment, unit: "EUR" });
  if (price_level !== "premium")
    changes.push({ label: "Product price level", old: "premium", new: price_level });

  const baseline: ComparisonSummary = {
    decision: baseReport.decision.label,
    break_even_probability: baseReport.financials.break_even_probability,
    expected_monthly_revenue: baseReport.financials.expected_monthly_revenue,
    expected_monthly_profit: baseReport.financials.expected_monthly_profit,
    risk_level: baseReport.decision.risk_level,
  };

  const adjusted: ComparisonSummary = {
    decision: new_decision,
    break_even_probability: Math.round(new_bep * 100) / 100,
    expected_monthly_revenue: new_revenue,
    expected_monthly_profit: new_profit,
    risk_level: new_risk,
  };

  return {
    baseline,
    adjusted,
    changed_assumptions: changes,
    impact_summary: buildWhatIfSummary(changes, baseline.decision, new_decision),
  };
}

// ─── Add market factor ────────────────────────────────────────────────────────

/**
 * Simulate adding a new external signal through the forecasting pipeline.
 * In production this kicks off a Sybilion forecast job for the new factor.
 *
 * TODO: Replace with real call:
 *   fetch('/api/add-factor', { method: 'POST',
 *     body: JSON.stringify({ factor_description, base_job_id }) }).then(r => r.json())
 * TODO: This should return a job_id that is polled for status, not a direct result.
 */
export async function mockAddMarketFactor(
  factorDescription: string,
  baseReport: Report,
): Promise<AddMarketFactorResult> {
  await delay(1600); // simulate forecast pipeline

  const keywords = extractKeywords(factorDescription);
  const impact = classifyImpact(factorDescription);

  const new_revenue = Math.round(
    baseReport.financials.expected_monthly_revenue * (1 + impact.revenue_delta_pct),
  );
  const new_profit = Math.round(
    baseReport.financials.expected_monthly_profit -
      impact.cost_increase_eur +
      (new_revenue - baseReport.financials.expected_monthly_revenue) * 0.35,
  );
  const profit_margin = new_revenue > 0 ? new_profit / new_revenue : -1;
  const new_decision = deriveVerdict(profit_margin);
  const new_bep = Math.max(
    0.05,
    Math.min(0.97, baseReport.financials.break_even_probability - impact.cost_increase_eur / 10000),
  );
  const new_risk = deriveRiskFromBep(new_bep); // keep risk consistent with break-even

  const baseline: ComparisonSummary = {
    decision: baseReport.decision.label,
    break_even_probability: baseReport.financials.break_even_probability,
    expected_monthly_revenue: baseReport.financials.expected_monthly_revenue,
    expected_monthly_profit: baseReport.financials.expected_monthly_profit,
    risk_level: baseReport.decision.risk_level,
  };

  const adjusted: ComparisonSummary = {
    decision: new_decision,
    break_even_probability: Math.round(new_bep * 100) / 100,
    expected_monthly_revenue: new_revenue,
    expected_monthly_profit: new_profit,
    risk_level: new_risk,
  };

  const reason = buildFactorReason(factorDescription, impact);

  return {
    status: "added",
    factor: { description: factorDescription, keywords },
    comparison: {
      baseline,
      adjusted,
      added_factor: { description: factorDescription, keywords },
      impact_summary: reason,
    },
    reason_for_update: reason,
  };
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function deriveVerdict(profit_margin: number): string {
  if (profit_margin > 0.15) return "Launch";
  if (profit_margin > 0.05) return "Adapt concept";
  if (profit_margin > 0) return "Delay";
  return "Do not launch";
}

// Derives risk from break-even probability so it stays consistent with BEP.
// Thresholds mirror the BREAK_EVEN_MAP in api.ts (0.80/0.60/0.40/0.20).
function deriveRiskFromBep(bep: number): string {
  if (bep >= 0.75) return "Low";
  if (bep >= 0.55) return "Medium-low";
  if (bep >= 0.38) return "Medium";
  if (bep >= 0.22) return "Medium-high";
  return "High";
}

function buildWhatIfSummary(
  changes: ChangedAssumption[],
  oldDecision: string,
  newDecision: string,
): string {
  if (changes.length === 0) return "No assumptions were changed from the baseline.";
  const labels = changes.map((c) => c.label.toLowerCase()).join(", ");
  if (oldDecision === newDecision)
    return `Adjusting ${labels} shifted the metrics but did not change the verdict.`;
  return `Adjusting ${labels} changed the verdict from "${oldDecision}" to "${newDecision}".`;
}

function extractKeywords(description: string): string[] {
  const STOP = new Set([
    "a",
    "an",
    "the",
    "for",
    "in",
    "of",
    "at",
    "to",
    "by",
    "and",
    "or",
    "with",
    "from",
    "that",
    "this",
    "on",
    "as",
    "is",
    "are",
    "was",
    "were",
    "per",
  ]);
  return [
    ...new Set(
      description
        .toLowerCase()
        .replace(/[^a-z\s]/g, " ")
        .split(/\s+/)
        .filter((w) => w.length >= 4 && !STOP.has(w)),
    ),
  ].slice(0, 5);
}

interface ImpactParams {
  revenue_delta_pct: number;
  cost_increase_eur: number;
  type: "cost" | "demand" | "competition" | "neutral";
}

function classifyImpact(description: string): ImpactParams {
  const d = description.toLowerCase();
  if (/energy|utilities|overhead|expense|cost|electricity|rent/.test(d))
    return { revenue_delta_pct: 0, cost_increase_eur: 1400, type: "cost" };
  if (/demand|tourism|visitor|spend|footfall|traffic/.test(d))
    return { revenue_delta_pct: 0.06, cost_increase_eur: 200, type: "demand" };
  if (/competition|competitor|rival|market.saturation/.test(d))
    return { revenue_delta_pct: -0.07, cost_increase_eur: 300, type: "competition" };
  return { revenue_delta_pct: 0, cost_increase_eur: 900, type: "neutral" };
}

function buildFactorReason(description: string, impact: ImpactParams): string {
  switch (impact.type) {
    case "cost":
      return `The added factor "${description}" increases expected operating costs, reducing monthly profit and lowering the break-even probability.`;
    case "demand":
      return `The added factor "${description}" reveals an additional demand signal that improves the revenue outlook.`;
    case "competition":
      return `The added factor "${description}" introduces competitive pressure, reducing the addressable customer base and lowering revenue.`;
    default:
      return `The added factor "${description}" has been incorporated into the analysis and modestly increases cost pressure.`;
  }
}

// Re-export type so components can import it without going to types.ts directly
export type { AddedMarketFactor };
