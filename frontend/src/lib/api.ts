import type {
  Report,
  DecisionLabel,
  RiskLevel,
  DriverDirection,
  Driver,
  InvestmentItem,
  HistoricalPoint,
  ForecastBandPoint,
  Backtest,
} from "./types";

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
    throw new Error("Backend returned a non-JSON response. Check the /api/extract endpoint.");
  }

  if (
    typeof data !== "object" ||
    data === null ||
    !("descriptions" in data) ||
    !Array.isArray((data as { descriptions: unknown }).descriptions)
  ) {
    throw new Error("Backend returned an unexpected shape — expected { descriptions: string[] }.");
  }

  return data as ExtractDescriptionsResponse;
}

// ─── Full-report shape guard ──────────────────────────────────────────────────
// Must be declared before confirmDescriptionsWithEndpoint which calls it.

const VALID_LABELS = new Set<DecisionLabel>(["Launch", "Adapt concept", "Delay", "Do not launch"]);

function isFullReport(data: unknown): data is Report {
  if (typeof data !== "object" || data === null) return false;
  const d = data as Record<string, unknown>;
  if (typeof d.decision !== "object" || d.decision === null) return false;
  const dec = d.decision as Record<string, unknown>;
  // Only accept if label is a known display label — backend codes like "no-go"
  // are not in DecisionOverview's STYLE map and would cause a hard crash.
  if (!VALID_LABELS.has(dec.label as DecisionLabel)) return false;
  return (
    typeof d.financials === "object" &&
    d.financials !== null &&
    typeof d.reason === "object" &&
    d.reason !== null
  );
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
export async function confirmDescriptionsWithEndpoint(descriptions: string[]): Promise<Report> {
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
    throw new Error(`Backend forecast confirmation failed (HTTP ${response.status}).`);
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
  // 1. Already the internal Report shape (has `financials`) — pass through.
  //    Guarded so an internal code label ("no-go") can't crash DecisionOverview.
  if (isFullReport(data)) {
    return data;
  }

  // 2. The report_agent §5.6 shape (decision + expected_revenue/graphs/…). The
  //    current backend returns this — map it into the internal Report.
  if (isConfirmReport(data)) {
    return adaptConfirmResponseToReport(data as ConfirmReportResponse);
  }

  // 3. Otherwise it's the legacy judgment format — adapt it.
  return adaptLegacyResponse(data as LegacyConfirmResponse);
}

// ─── Adapter: legacy backend format → Report ─────────────────────────────────

const VERDICT_MAP: Record<string, DecisionLabel> = {
  // backend codes
  go: "Launch",
  "no-go": "Do not launch",
  adapt: "Adapt concept",
  delay: "Delay",
  // in case backend sends the display label directly
  Launch: "Launch",
  "Do not launch": "Do not launch",
  "Adapt concept": "Adapt concept",
  Delay: "Delay",
};

const RISK_MAP: Record<DecisionLabel, RiskLevel> = {
  Launch: "Low",
  "Adapt concept": "Medium",
  Delay: "Medium-high",
  "Do not launch": "High",
};

const BREAK_EVEN_MAP: Record<DecisionLabel, number> = {
  Launch: 0.8,
  "Adapt concept": 0.6,
  Delay: 0.4,
  "Do not launch": 0.2,
};

function adaptLegacyResponse(raw: LegacyConfirmResponse): Report {
  const j = raw.judgment ?? {};

  // VERDICT_MAP handles both backend codes ("no-go") and display labels ("Do not launch").
  const label: DecisionLabel = VERDICT_MAP[j.verdict ?? ""] ?? "Adapt concept";

  // Safely convert unknown values to string arrays — backend might send null,
  // a plain string, or an object instead of string[].
  const toStrArr = (v: unknown): string[] =>
    Array.isArray(v) ? (v as string[]).map(String) : typeof v === "string" && v ? [v] : [];

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
      confidence: 0.7,
      summary: j.summary ?? "",
    },
    financials: {
      expected_monthly_revenue: j.estimated_monthly_revenue_eur ?? 0,
      expected_monthly_costs: j.estimated_monthly_costs_eur ?? 0,
      expected_monthly_profit: j.estimated_monthly_profit_eur ?? 0,
      estimated_initial_investment: 0,
      break_even_probability: BREAK_EVEN_MAP[label],
      payback_period_months: j.payback_months ?? 0,
    },
    // graphs, drivers, investment_breakdown, backtest not provided by legacy backend
    graphs: undefined,
    drivers: undefined,
    investment_breakdown: undefined,
    backtest: null,
    reason: {
      main_reason: typeof j.summary === "string" ? j.summary : "",
      positive_factors: toStrArr(j.strengths),
      negative_factors: toStrArr(j.risks),
      recommended_actions: toStrArr(j.recommendation),
    },
  };
}

// ─── Adapter: backend report_agent §5.6 format → internal Report ──────────────
// The current backend (POST /api/confirm) returns the report_agent shape, NOT
// the internal Report shape the dashboard reads. The two differ in field names
// (`expected_revenue.*_eur` vs `financials.*`), graph-point keys
// ({date,historical,forecast,low,high} vs {month,value}/{month,low,mid,high}),
// and MAPE scale (fraction vs percent). This bridges that gap so the dashboard
// shows real financials, a continuous forecast chart, drivers, and reasoning.

// Loose mirror of the §5.6 payload — every field optional because a fallback
// run on the backend can omit any of them; the adapter fills gaps safely.
export type ConfirmReportResponse = {
  decision?: {
    label?: string;
    score?: number;
    risk_level?: string;
    confidence?: number;
    summary?: string;
  };
  expected_revenue?: {
    expected_monthly_revenue_eur?: number;
    expected_monthly_costs_eur?: number;
    expected_monthly_profit_eur?: number;
    break_even_probability?: number;
    payback_months?: number | null;
  };
  investment_cost?: {
    estimated_initial_investment_eur?: number;
    breakdown?: Array<{ category?: string; amount?: number }>;
  };
  graphs?: {
    historical_series?: Array<{ date?: string; historical?: number | null }>;
    demand_forecast?: Array<{
      date?: string;
      forecast?: number | null;
      low?: number | null;
      high?: number | null;
    }>;
  };
  drivers?: Array<{ name?: string; importance?: number; direction?: string }>;
  backtest?: { mape?: number; quality?: string } | null;
  reason?: {
    main_reason?: string;
    positive_factors?: string[];
    negative_factors?: string[];
    recommended_actions?: string[];
  };
};

const DRIVER_DIRECTIONS = new Set<DriverDirection>(["positive", "negative", "mixed"]);

// FinancialProjection renders payback_period_months >= 999 as "—" (no payback).
const NO_PAYBACK_SENTINEL = 999;

/** Coerce an unknown value to a finite number, else `fallback`. Avoids NaN in the UI. */
function toNum(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

/** Keep only the string entries of an unknown value; never returns undefined. */
function toStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/**
 * Detect the report_agent §5.6 payload: a `decision` object alongside at least
 * one of its distinctive sibling sections. Distinguishes it from both the
 * internal Report (caught earlier by isFullReport) and the legacy judgment shape.
 */
function isConfirmReport(data: unknown): data is ConfirmReportResponse {
  if (typeof data !== "object" || data === null) return false;
  const d = data as Record<string, unknown>;
  if (typeof d.decision !== "object" || d.decision === null) return false;
  return "expected_revenue" in d || "graphs" in d || "investment_cost" in d;
}

/**
 * Map the backend §5.6 report into the internal Report. Field names below were
 * verified against types.ts and each consuming component (FinancialProjection,
 * ForecastChart, DriverImportanceChart, InvestmentBreakdown, BacktestBadge,
 * ReasoningCard, DecisionOverview). Missing/null fields degrade gracefully.
 */
export function adaptConfirmResponseToReport(raw: ConfirmReportResponse): Report {
  const dec = raw.decision ?? {};
  const rev = raw.expected_revenue ?? {};
  const inv = raw.investment_cost ?? {};
  const graphs = raw.graphs ?? {};
  const reason = raw.reason ?? {};

  // decision.label is used as a key into DecisionOverview's STYLE map — an
  // unknown value would crash it, so fall back to a safe display label.
  const label: DecisionLabel = VALID_LABELS.has(dec.label as DecisionLabel)
    ? (dec.label as DecisionLabel)
    : "Adapt concept";

  // Backend payback_months is a positive int OR null ("never pays back").
  // The internal field uses the >= 999 sentinel that FinancialProjection shows as "—".
  const payback = rev.payback_months;
  const payback_period_months =
    typeof payback === "number" && Number.isFinite(payback) ? payback : NO_PAYBACK_SENTINEL;

  // graphs.historical_series[{date,historical}] → [{month,value}]
  const historical_series: HistoricalPoint[] = (graphs.historical_series ?? []).map((p) => ({
    month: p.date ?? "",
    value: toNum(p.historical),
  }));

  // graphs.demand_forecast[{date,forecast,low,high}] → [{month,low,mid,high}]
  const demand_forecast: ForecastBandPoint[] = (graphs.demand_forecast ?? []).map((p) => ({
    month: p.date ?? "",
    low: toNum(p.low),
    mid: toNum(p.forecast),
    high: toNum(p.high),
  }));

  const drivers: Driver[] = (raw.drivers ?? []).map((dr) => ({
    name: dr.name ?? "",
    importance: toNum(dr.importance),
    direction: DRIVER_DIRECTIONS.has(dr.direction as DriverDirection)
      ? (dr.direction as DriverDirection)
      : "mixed",
    // Backend `horizon` is a scalar (months ahead), not the {month_1,month_6}
    // shift map DriverImportanceChart reads — omit it so the chart degrades
    // gracefully (it simply hides the horizon-shift bar).
  }));

  const investment_breakdown: InvestmentItem[] = (inv.breakdown ?? []).map((it) => ({
    category: it.category ?? "",
    amount: toNum(it.amount),
  }));

  // Backend MAPE is a fraction (0.12); BacktestBadge renders `{mape}%`, so → percent.
  const backtest: Backtest | null = raw.backtest
    ? {
        quality: raw.backtest.quality ?? "medium",
        mape: Math.round(toNum(raw.backtest.mape) * 1000) / 10,
      }
    : null;

  const hasGraphs = historical_series.length > 0 || demand_forecast.length > 0;

  return {
    decision: {
      label,
      score: Math.round(toNum(dec.score)),
      risk_level: (dec.risk_level as RiskLevel) ?? "Medium",
      confidence: toNum(dec.confidence),
      summary: dec.summary ?? "",
    },
    financials: {
      expected_monthly_revenue: toNum(rev.expected_monthly_revenue_eur),
      expected_monthly_costs: toNum(rev.expected_monthly_costs_eur),
      expected_monthly_profit: toNum(rev.expected_monthly_profit_eur),
      estimated_initial_investment: toNum(inv.estimated_initial_investment_eur),
      break_even_probability: toNum(rev.break_even_probability),
      payback_period_months,
    },
    // Only attach optional sections when populated so the dashboard's
    // `report.graphs && …` / `?.length` guards hide empty cards instead of
    // rendering broken ones.
    graphs: hasGraphs ? { historical_series, demand_forecast } : undefined,
    drivers: drivers.length ? drivers : undefined,
    investment_breakdown: investment_breakdown.length ? investment_breakdown : undefined,
    reason: {
      main_reason: reason.main_reason ?? "",
      positive_factors: toStringArray(reason.positive_factors),
      negative_factors: toStringArray(reason.negative_factors),
      recommended_actions: toStringArray(reason.recommended_actions),
    },
    backtest,
  };
}
