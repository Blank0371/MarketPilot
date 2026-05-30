import { mockDescriptions, mockReport, ECONOMICS } from "./mockData";
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

// ─── Extract ─────────────────────────────────────────────────────────────────

/**
 * TODO: Replace with real call:
 *   fetch('/api/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ userInput }) }).then(r => r.json()) as Promise<DescriptionsPayload>
 */
export async function extract(userInput: string): Promise<DescriptionsPayload> {
  await delay(1100);
  void userInput;
  return { descriptions: [...mockDescriptions] };
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
  return structuredClone(mockReport);
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

  // ── Read overrides (fall back to base values from ECONOMICS) ──────────────
  const basket = (overrides["average_basket_size"] as number) ?? ECONOMICS.base_basket_size;
  const margin = (overrides["gross_margin"] as number) ?? 0.35;
  const staffing = (overrides["staffing_level"] as number) ?? 1;
  const days = (overrides["opening_days_per_month"] as number) ?? ECONOMICS.base_opening_days;
  const investment = (overrides["initial_investment_budget"] as number) ?? 120000;
  const price_level = (overrides["product_price_level"] as string) ?? "premium";

  const demand_mult = DEMAND_MULT[price_level] ?? 1.0;

  // ── Revenue ───────────────────────────────────────────────────────────────
  const new_revenue = Math.round(
    ECONOMICS.daily_customers * basket * days * demand_mult,
  );

  // ── Costs ─────────────────────────────────────────────────────────────────
  const cogs = new_revenue * (1 - margin);
  const staff_cost = staffing * ECONOMICS.staff_cost_per_employee;
  const new_costs = Math.round(cogs + staff_cost + ECONOMICS.fixed_overhead);
  const new_profit = new_revenue - new_costs;
  const profit_margin = new_revenue > 0 ? new_profit / new_revenue : -1;

  // ── Verdict ───────────────────────────────────────────────────────────────
  const new_decision = deriveVerdict(profit_margin);
  const new_risk = deriveRiskLevel(profit_margin);
  const new_bep = Math.max(0.05, Math.min(0.97, 0.35 + profit_margin * 2.5));
  const payback = new_profit > 0 ? Math.round(investment / new_profit) : 999;
  void payback; // payback used in fuller reports; included here for completeness

  // ── Changed assumptions ───────────────────────────────────────────────────
  const changes: ChangedAssumption[] = [];
  if (Math.abs(basket - ECONOMICS.base_basket_size) > 0.01)
    changes.push({ label: "Average basket size", old: ECONOMICS.base_basket_size, new: basket, unit: "EUR" });
  if (Math.abs(margin - 0.35) > 0.001)
    changes.push({ label: "Gross margin", old: 0.35, new: margin, unit: "%" });
  if (staffing !== 1)
    changes.push({ label: "Staffing level", old: 1, new: staffing, unit: "employees" });
  if (days !== ECONOMICS.base_opening_days)
    changes.push({ label: "Opening days per month", old: ECONOMICS.base_opening_days, new: days, unit: "days" });
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
    baseReport.financials.expected_monthly_profit
    - impact.cost_increase_eur
    + (new_revenue - baseReport.financials.expected_monthly_revenue) * 0.35,
  );
  const profit_margin = new_revenue > 0 ? new_profit / new_revenue : -1;
  const new_decision = deriveVerdict(profit_margin);
  const new_risk = deriveRiskLevel(profit_margin);
  const new_bep = Math.max(
    0.05,
    Math.min(0.97, baseReport.financials.break_even_probability - impact.cost_increase_eur / 10000),
  );

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

function deriveRiskLevel(profit_margin: number): string {
  if (profit_margin > 0.15) return "Low";
  if (profit_margin > 0.08) return "Medium-low";
  if (profit_margin > 0.03) return "Medium";
  if (profit_margin > 0) return "Medium-high";
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
    "a","an","the","for","in","of","at","to","by","and","or","with",
    "from","that","this","on","as","is","are","was","were","per",
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
