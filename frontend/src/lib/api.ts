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

// Legacy format returned by the current backend (Block 4 judgment shape).
// Kept until Block 4 migrates to returning a full Report shape directly.
export type LegacyConfirmResponse = {
  session_id?: string;
  round?: number;
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
  };
  forecast_summary?: {
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

const CONFIRM_TIMEOUT_MS = 1_200_000; // 20 minutes — Sybilion pipeline can be slow

/**
 * POST /api/confirm — send confirmed descriptions, receive a Report.
 *
 * Accepts two backend shapes transparently:
 *   • Legacy: { judgment: { verdict, score, ... }, forecast_summary }
 *   • Future: full Report shape (once Block 4 migrates)
 *
 * The fallback Report (typically mockReport) fills fields the legacy format
 * does not provide (graphs, drivers, investment_breakdown, backtest).
 */
export async function confirmDescriptionsWithEndpoint(
  descriptions: string[],
): Promise<Report> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIRM_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${BACKEND_BASE}/api/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descriptions }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(
        `Backend did not respond within ${CONFIRM_TIMEOUT_MS / 60000} minutes. Check that the backend is running on ${BACKEND_BASE}.`,
      );
    }
    throw new Error(
      `Backend forecast confirmation failed. Check that the backend is running on ${BACKEND_BASE}.`,
    );
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    throw new Error(
      `Backend forecast confirmation failed (HTTP ${response.status}).`,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error("Backend returned a non-JSON response from /api/confirm.");
  }

  if (typeof data !== "object" || data === null) {
    throw new Error("Backend /api/confirm returned an unexpected shape.");
  }

  // ── Format detection ────────────────────────────────────────────────────────
  // If the response already has a `decision` field it's the new full Report shape.
  if ("decision" in data && (data as Record<string, unknown>).decision) {
    return data as Report;
  }

  // Otherwise it's the legacy judgment format — adapt it.
  return adaptLegacyResponse(data as LegacyConfirmResponse);
}

// ─── Adapter: legacy backend format → Report ─────────────────────────────────

const VERDICT_MAP: Record<string, DecisionLabel> = {
  go:      "Launch",
  "no-go": "Do not launch",
  adapt:   "Adapt concept",
  delay:   "Delay",
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

function adaptLegacyResponse(raw: LegacyConfirmResponse): Report {
  const j = raw.judgment ?? {};

  const label: DecisionLabel = VERDICT_MAP[j.verdict ?? ""] ?? "Adapt concept";

  // Backend score may be 0-1, 0-10, or 0-100; normalise to 0-100.
  const rawScore = j.score ?? 50;
  const score = Math.round(
    rawScore <= 1 ? rawScore * 100 : rawScore <= 10 ? rawScore * 10 : Math.min(rawScore, 100),
  );

  return {
    decision: {
      label,
      score,
      risk_level: RISK_MAP[label],
      confidence: 0.70,
      summary: j.summary ?? "",
    },
    financials: {
      expected_monthly_revenue: j.estimated_monthly_revenue_eur ?? 0,
      expected_monthly_costs:   j.estimated_monthly_costs_eur   ?? 0,
      expected_monthly_profit:  j.estimated_monthly_profit_eur  ?? 0,
      estimated_initial_investment: 0,
      break_even_probability: BREAK_EVEN_MAP[label],
      payback_period_months:  j.payback_months ?? 0,
    },
    // graphs, drivers, investment_breakdown, backtest not provided by legacy backend
    graphs: undefined,
    drivers: undefined,
    investment_breakdown: undefined,
    backtest: null,
    reason: {
      main_reason: j.summary ?? "",
      positive_factors:    (j.strengths      as string[] | undefined) ?? [],
      negative_factors:    (j.risks          as string[] | undefined) ?? [],
      recommended_actions: j.recommendation ? [j.recommendation]     : [],
    },
  };
}

