import type { Report, DecisionLabel, RiskLevel } from "./types";

// Temporary dev control for switching between mock data and backend endpoint.
export type DataMode = "mock" | "endpoint";

// ─── Types ────────────────────────────────────────────────────────────────────

export type ExtractDescriptionsResponse = {
  descriptions: string[];
};

export type ConfirmDescriptionsRequest = {
  descriptions: string[];
};

export type ConfirmDescriptionsResponse = {
  session_id?: string;
  round?: number;
  conversation_turns?: number;
  judgment?: {
    verdict?: string;
    score?: number;
    summary?: string;
    estimated_monthly_revenue_eur?: number;
    estimated_monthly_costs_eur?: number;
    estimated_monthly_profit_eur?: number;
    payback_months?: number;
    strengths?: string[];
    risks?: string[];
    recommendation?: string;
    changed_from_previous?: string | null;
  };
  forecast_summary?: {
    statistic_title?: string;
    keywords?: string[];
    observations?: number;
    forecast_horizon?: number;
    forecast_series?: Record<string, number>;
    top_drivers?: unknown[];
  };
};

// ─── Config ───────────────────────────────────────────────────────────────────

const BACKEND_BASE = "http://127.0.0.1:8003";

// ─── Extraction endpoint ──────────────────────────────────────────────────────

/**
 * POST /api/extract — send a free-form business idea and receive a list of
 * market signal descriptions from the backend extraction agent.
 *
 * Throws a user-readable error when:
 * - the network request fails (backend not running, CORS, etc.)
 * - the HTTP response is not 2xx
 * - the response body is not valid JSON
 * - the response shape is not { descriptions: string[] }
 */
export async function extractDescriptionsFromEndpoint(
  userInput: string,
): Promise<ExtractDescriptionsResponse> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_BASE}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userInput }),
    });
  } catch {
    throw new Error(
      `Backend extraction failed. Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  if (!response.ok) {
    throw new Error(
      `Backend extraction failed (HTTP ${response.status}). Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "Backend returned a non-JSON response. Check the /api/extract endpoint.",
    );
  }

  if (
    typeof data !== "object" ||
    data === null ||
    !("descriptions" in data) ||
    !Array.isArray((data as { descriptions: unknown }).descriptions)
  ) {
    throw new Error(
      "Backend returned an unexpected shape — expected { descriptions: string[] }.",
    );
  }

  return data as ExtractDescriptionsResponse;
}

// ─── Confirmation endpoint ────────────────────────────────────────────────────

/**
 * POST /api/confirm — send confirmed descriptions and receive a synchronous
 * pipeline result (judgment + forecast summary).
 *
 * Unlike the mock flow, this backend call is synchronous: no job polling needed.
 * The caller should show a loading state while the request is in-flight.
 */
export async function confirmDescriptionsWithEndpoint(
  descriptions: string[],
): Promise<ConfirmDescriptionsResponse> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_BASE}/api/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descriptions }),
    });
  } catch {
    throw new Error(
      `Backend forecast confirmation failed. Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  if (!response.ok) {
    throw new Error(
      `Backend forecast confirmation failed (HTTP ${response.status}). Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "Backend returned a non-JSON response from /api/confirm.",
    );
  }

  if (typeof data !== "object" || data === null) {
    throw new Error(
      "Backend /api/confirm returned an unexpected shape — expected an object.",
    );
  }

  return data as ConfirmDescriptionsResponse;
}

// ─── Adapter: backend confirm response → dashboard Report ─────────────────────

const VERDICT_MAP: Record<string, DecisionLabel> = {
  go:     "Launch",
  "no-go": "Do not launch",
  adapt:  "Adapt concept",
};

const RISK_MAP: Record<DecisionLabel, RiskLevel> = {
  Launch:          "Low",
  "Adapt concept": "Medium",
  Delay:           "Medium-high",
  "Do not launch": "High",
};

const BREAK_EVEN_MAP: Record<DecisionLabel, number> = {
  Launch:          0.80,
  "Adapt concept": 0.60,
  Delay:           0.40,
  "Do not launch": 0.20,
};

/**
 * Map a ConfirmDescriptionsResponse into the Report shape expected by the
 * dashboard. Uses `fallback` (typically mockReport) for fields the backend
 * does not yet provide (graphs, investment_breakdown, drivers, backtest).
 *
 * Remove or replace this adapter when the backend returns a full Report shape.
 */
export function adaptConfirmResponseToReport(
  resp: ConfirmDescriptionsResponse,
  fallback: Report,
): Report {
  const j = resp.judgment ?? {};

  const label: DecisionLabel = VERDICT_MAP[j.verdict ?? ""] ?? "Adapt concept";

  // Backend score may be 0-1 or 0-100; normalise to 0-100.
  const rawScore = j.score ?? 50;
  const score = Math.round(rawScore > 1 ? Math.min(rawScore, 100) : rawScore * 100);

  const positive = (j.strengths ?? []).length > 0
    ? (j.strengths as string[])
    : fallback.reason.positive_factors;

  const negative = (j.risks ?? []).length > 0
    ? (j.risks as string[])
    : fallback.reason.negative_factors;

  const actions = j.recommendation
    ? [j.recommendation]
    : fallback.reason.recommended_actions;

  return {
    decision: {
      label,
      score,
      risk_level: RISK_MAP[label],
      confidence: 0.70,
      summary: j.summary ?? fallback.decision.summary,
    },
    financials: {
      expected_monthly_revenue:
        j.estimated_monthly_revenue_eur ?? fallback.financials.expected_monthly_revenue,
      expected_monthly_costs:
        j.estimated_monthly_costs_eur ?? fallback.financials.expected_monthly_costs,
      expected_monthly_profit:
        j.estimated_monthly_profit_eur ?? fallback.financials.expected_monthly_profit,
      estimated_initial_investment: fallback.financials.estimated_initial_investment,
      break_even_probability: BREAK_EVEN_MAP[label],
      payback_period_months:
        j.payback_months ?? fallback.financials.payback_period_months,
    },
    graphs: fallback.graphs,
    drivers: fallback.drivers,
    investment_breakdown: fallback.investment_breakdown,
    reason: {
      main_reason: j.summary ?? fallback.reason.main_reason,
      positive_factors: positive,
      negative_factors: negative,
      recommended_actions: actions,
    },
    backtest: fallback.backtest,
  };
}
