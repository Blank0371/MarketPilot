// ─── API / Pipeline ───────────────────────────────────────────────────────────

export interface DescriptionsPayload {
  descriptions: string[];
}

export interface ConfirmResponse {
  job_id: string;
}

export type PipelineStep =
  | "extracting"
  | "fetching"
  | "forecasting"
  | "reporting"
  | "done";

export interface JobStatus {
  job_id: string;
  step: PipelineStep;
  done: boolean;
  error?: string;
}

// ─── Report ───────────────────────────────────────────────────────────────────

export type DecisionLabel = "Launch" | "Adapt concept" | "Delay" | "Do not launch";
export type RiskLevel = "Low" | "Medium-low" | "Medium" | "Medium-high" | "High";
export type DriverDirection = "positive" | "negative" | "mixed";

export interface HistoricalPoint {
  month: string;
  value: number;
}

export interface ForecastBandPoint {
  month: string;
  low: number;
  mid: number;
  high: number;
}

export interface GraphsData {
  historical_series: HistoricalPoint[];
  demand_forecast: ForecastBandPoint[];
}

export interface Driver {
  name: string;
  importance: number;
  direction: DriverDirection;
  horizon?: Record<string, number>;
  explanation?: string;
}

export interface InvestmentItem {
  category: string;
  amount: number;
}

export interface Backtest {
  quality: string;
  mape: number;
}

export interface Report {
  decision: {
    label: DecisionLabel;
    score: number;
    risk_level: RiskLevel;
    confidence: number;
    summary: string;
  };
  financials: {
    expected_monthly_revenue: number;
    expected_monthly_costs: number;
    expected_monthly_profit: number;
    estimated_initial_investment: number;
    break_even_probability: number;
    payback_period_months: number;
  };
  graphs: GraphsData;
  drivers: Driver[];
  investment_breakdown: InvestmentItem[];
  reason: {
    main_reason: string;
    positive_factors: string[];
    negative_factors: string[];
    recommended_actions: string[];
  };
  backtest: Backtest;
}

// ─── What-if overrides ────────────────────────────────────────────────────────

export type OverrideType = "currency" | "percentage" | "number" | "select";

export interface AllowedOverride {
  id: string;
  label: string;
  type: OverrideType;
  unit?: string;
  base_value: number | string;
  min?: number;
  max?: number;
  options?: string[];
  description?: string;
}

export type OverrideValue = number | string;
export type OverridesMap = Record<string, OverrideValue>;

// ─── Comparison (shared by What-if and Add-factor) ───────────────────────────

export interface ComparisonSummary {
  decision: string;
  break_even_probability: number;
  expected_monthly_revenue: number;
  expected_monthly_profit: number;
  risk_level: string;
}

export interface ChangedAssumption {
  label: string;
  old: number | string;
  new: number | string;
  unit?: string;
}

export interface ComparisonResult {
  baseline: ComparisonSummary;
  adjusted: ComparisonSummary;
  changed_assumptions?: ChangedAssumption[];
  added_factor?: {
    description: string;
    keywords: string[];
  };
  impact_summary: string;
}

// ─── Add market factor ────────────────────────────────────────────────────────

export interface AddedMarketFactor {
  description: string;
  keywords: string[];
  status: "queued" | "running" | "added" | "failed";
  reason_for_update?: string;
}

export interface AddMarketFactorResult {
  status: "added";
  factor: {
    description: string;
    keywords: string[];
  };
  comparison: ComparisonResult;
  reason_for_update: string;
}

// ─── Navigation / UI helpers ─────────────────────────────────────────────────

export interface NavLink {
  label: string;
  href: string;
}

export interface StepDefinition {
  id: 1 | 2 | 3;
  label: string;
  description: string;
}
