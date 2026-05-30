// ─── API Contracts ────────────────────────────────────────────────────────────

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
export type RiskLevel = "Low" | "Medium" | "High";
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
  /** Importance per horizon: e.g. { month_1: 0.85, month_6: 0.42 } */
  horizon?: Record<string, number>;
  explanation?: string;
}

export interface InvestmentItem {
  category: string;
  amount: number;
}

export interface Backtest {
  /** Human-readable quality label, e.g. "medium-high" */
  quality: string;
  /** Mean Absolute Percentage Error (0–100) */
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

// ─── What-if ──────────────────────────────────────────────────────────────────

export interface WhatIfOverrides {
  monthly_rent?: number;
  average_basket_price?: number;
  gross_margin_pct?: number;
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
