import { mockDescriptions, mockReport, BASELINE } from "./mockData";
import type {
  DescriptionsPayload,
  ConfirmResponse,
  JobStatus,
  PipelineStep,
  Report,
  WhatIfOverrides,
  DecisionLabel,
} from "./types";

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// Tracks job start time so polling can simulate step advancement by elapsed time.
const jobRegistry = new Map<string, number>();

// ─── Extract ─────────────────────────────────────────────────────────────────

/**
 * Extract standardized market-factor descriptions from a free-text business pitch.
 *
 * TODO: Replace with the real call:
 *   fetch('/api/extract', {
 *     method: 'POST',
 *     headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ userInput }),
 *   }).then(r => r.json()) as Promise<DescriptionsPayload>
 */
export async function extract(userInput: string): Promise<DescriptionsPayload> {
  await delay(1100);
  void userInput;
  return { descriptions: [...mockDescriptions] };
}

// ─── Confirm ─────────────────────────────────────────────────────────────────

/**
 * Send the user-confirmed (edited) descriptions to the backend.
 * Returns a job_id for polling.
 *
 * TODO: Replace with the real call:
 *   fetch('/api/confirm', {
 *     method: 'POST',
 *     headers: { 'Content-Type': 'application/json' },
 *     body: JSON.stringify({ descriptions }),
 *   }).then(r => r.json()) as Promise<ConfirmResponse>
 */
export async function confirm(descriptions: string[]): Promise<ConfirmResponse> {
  await delay(350);
  void descriptions;
  const job_id = `job_${Date.now()}`;
  jobRegistry.set(job_id, Date.now());
  return { job_id };
}

// ─── Status polling ──────────────────────────────────────────────────────────

const STEP_SCHEDULE: Array<{ after_ms: number; step: PipelineStep }> = [
  { after_ms: 0, step: "extracting" },
  { after_ms: 2800, step: "fetching" },
  { after_ms: 5600, step: "forecasting" },
  { after_ms: 8800, step: "reporting" },
  { after_ms: 11500, step: "done" },
];

/**
 * Poll the pipeline status for a given job.
 * Steps advance based on elapsed time since job creation.
 *
 * TODO: Replace with the real call:
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
 * Fetch the final report once the job reaches "done".
 *
 * TODO: Replace with the real call:
 *   fetch(`/api/result/${job_id}`).then(r => r.json()) as Promise<Report>
 */
export async function getResult(job_id: string): Promise<Report> {
  await delay(200);
  void job_id;
  return structuredClone(mockReport);
}

// ─── What-if recompute ────────────────────────────────────────────────────────

/**
 * Locally recompute the verdict and financials when the user adjusts assumptions.
 *
 * This is the decision intelligence layer: the same economics the backend runs,
 * but client-side for instant feedback.
 *
 * TODO: Point at a fast backend recompute endpoint when available:
 *   fetch('/api/recompute', {
 *     method: 'POST',
 *     body: JSON.stringify({ report, overrides }),
 *   }).then(r => r.json()) as Promise<Report>
 */
export function recompute(base: Report, overrides: WhatIfOverrides): Report {
  const rent = overrides.monthly_rent ?? BASELINE.monthly_rent;
  const basket = overrides.average_basket_price ?? BASELINE.average_basket_price;
  const margin = (overrides.gross_margin_pct ?? BASELINE.gross_margin_pct) / 100;

  // Revenue scales linearly with basket price (same customer volume).
  const new_revenue = BASELINE.customers_per_month * basket;

  // Costs: variable COGS + fixed rent + fixed staff + fixed overhead.
  const cogs = new_revenue * (1 - margin);
  const new_costs = Math.round(cogs + rent + BASELINE.staff_costs + BASELINE.other_overhead);
  const new_profit = Math.round(new_revenue - new_costs);
  const profit_margin = new_revenue > 0 ? new_profit / new_revenue : -1;

  // ── TODO (Learning opportunity) ──────────────────────────────────────────
  // Implement the verdict derivation logic below (5-10 lines).
  //
  // You decide:
  // - At what profit_margin threshold should the verdict flip to "Launch"?
  // - When does it drop to "Delay" or "Do not launch"?
  // - How should quality_score and confidence track with profitability?
  //
  // Hint: profit_margin = new_profit / new_revenue (e.g. 0.12 = 12% margin)
  // ─────────────────────────────────────────────────────────────────────────
  const label: DecisionLabel = deriveVerdict(profit_margin);
  const score = Math.max(5, Math.min(95, Math.round(50 + profit_margin * 250)));
  const confidence = Math.max(0.1, Math.min(0.95, parseFloat((0.5 + profit_margin * 1.5).toFixed(2))));

  const new_bep = Math.max(0.05, Math.min(0.97, parseFloat((0.35 + profit_margin * 2.5).toFixed(2))));
  const payback =
    new_profit > 0
      ? Math.round(base.financials.estimated_initial_investment / new_profit)
      : 999;

  return {
    ...base,
    decision: {
      ...base.decision,
      label,
      score,
      confidence,
      summary: buildSummary(label, rent, basket, margin),
    },
    financials: {
      ...base.financials,
      expected_monthly_revenue: Math.round(new_revenue),
      expected_monthly_costs: new_costs,
      expected_monthly_profit: new_profit,
      break_even_probability: new_bep,
      payback_period_months: payback,
    },
  };
}

/** Derive the decision label from the computed profit margin. */
function deriveVerdict(profit_margin: number): DecisionLabel {
  if (profit_margin > 0.15) return "Launch";
  if (profit_margin > 0.05) return "Adapt concept";
  if (profit_margin > 0) return "Delay";
  return "Do not launch";
}

function buildSummary(
  label: DecisionLabel,
  rent: number,
  basket: number,
  margin: number,
): string {
  const r = `€${rent.toLocaleString("en-US")}`;
  const b = `€${basket.toFixed(2)}`;
  const m = `${Math.round(margin * 100)}%`;
  switch (label) {
    case "Launch":
      return `At ${r} rent, ${b} basket, and ${m} margin — the numbers work. Go.`;
    case "Adapt concept":
      return `Viable at ${b} basket and ${m} margin, but the model is tight — any cost overrun flips the verdict.`;
    case "Delay":
      return `Margins are too thin at these inputs. Push the basket price above ${b} or cut fixed costs before committing.`;
    case "Do not launch":
      return `These assumptions produce negative margins. Major changes to rent, pricing, or cost structure are required.`;
  }
}
