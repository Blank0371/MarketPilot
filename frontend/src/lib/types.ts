export interface BusinessPitchInput {
  pitchText: string;
}

export interface Location {
  city: string;
  district: string;
  country: string;
}

export interface FinancialAssumptions {
  initial_investment: number;
  monthly_rent: number;
  staff_costs: number;
  average_basket_size: number;
  gross_margin: number;
  forecast_horizon_months: number;
}

export type ConfidenceLevel = "High" | "Medium" | "Low";

export interface ExtractedAssumptions {
  business_type: string;
  location: Location;
  sales_channels: string[];
  target_customers: string[];
  pricing_position: string;
  business_model: string;
  forecast_target: string;
  forecast_keywords: string[];
  confidence: {
    business_type: ConfidenceLevel;
    location: ConfidenceLevel;
    pricing_position: ConfidenceLevel;
    forecast_target: ConfidenceLevel;
  };
  financial_assumptions: FinancialAssumptions;
}

export interface ForecastPoint {
  month: string;
  p10: number;
  p50: number;
  p90: number;
}

export type DriverDirection = "positive" | "negative" | "mixed";

export interface Driver {
  name: string;
  importance: number;
  direction: DriverDirection;
}

export interface ReasoningItem {
  factor: string;
  impact: DriverDirection;
  explanation: string;
}

export type Recommendation =
  | "Launch"
  | "Adapt concept"
  | "Delay"
  | "Do not launch";

export type RiskScore = "Low" | "Medium" | "High";

export interface AnalysisResult {
  analysis_id: string;
  recommendation: Recommendation;
  break_even_probability: number;
  expected_monthly_profit: number;
  risk_score: RiskScore;
  downside_risk: number;
  forecast: ForecastPoint[];
  drivers: Driver[];
  reasoning: ReasoningItem[];
}

export interface ScenarioChange {
  monthly_rent?: number;
  average_basket_size?: number;
  competition_level?: number;
  gross_margin?: number;
}

export interface ScenarioMetricDelta {
  old: number;
  new: number;
}

export interface ScenarioResult {
  previous_recommendation: Recommendation;
  new_recommendation: Recommendation;
  previous_break_even_probability: number;
  new_break_even_probability: number;
  previous_expected_monthly_profit: number;
  new_expected_monthly_profit: number;
  changed_metrics: Record<string, ScenarioMetricDelta>;
  reason_for_change: string;
}

export interface ScenarioInitialValues {
  monthly_rent: number;
  average_basket_size: number;
  competition_level: number;
  gross_margin: number;
}

export interface NavLink {
  label: string;
  href: string;
}

export interface StepDefinition {
  id: 1 | 2 | 3;
  label: string;
  description: string;
}

/* ============================================================
 * Dynamic editable fields (returned by /extract endpoint)
 * ============================================================ */

export type EditableFieldType =
  | "text"
  | "number"
  | "select"
  | "tags"
  | "percentage"
  | "currency";

export type EditableFieldValue = string | number | string[];

export interface EditableField {
  key: string;
  label: string;
  type: EditableFieldType;
  value: EditableFieldValue;
  options?: string[];
  confidence?: ConfidenceLevel;
  helper?: string;
}

export interface EditableFieldGroup {
  category: string;
  fields: EditableField[];
}

/* ============================================================
 * Calculation result (returned by /calculate endpoint)
 * ============================================================ */

export type DecisionLabel =
  | "Launch"
  | "Adapt concept"
  | "Delay"
  | "Do not launch";

export interface ResultDecision {
  label: DecisionLabel;
  quality_score: number;
  risk_level: string;
  confidence: number;
  summary: string;
}

export interface ResultFinancials {
  expected_monthly_revenue: number;
  expected_monthly_costs: number;
  expected_monthly_profit: number;
  estimated_initial_investment: number;
  break_even_probability: number;
  payback_period_months: number;
}

export interface InvestmentItem {
  category: string;
  amount: number;
}

export interface ResultDriver {
  name: string;
  importance: number;
  direction: DriverDirection;
  explanation?: string;
}

export interface ResultReasoning {
  main_reason: string;
  positive_factors: string[];
  negative_factors: string[];
  recommended_actions: string[];
}

export type GraphsMap = Record<string, ForecastPoint[]>;

export interface CalculationResult {
  decision: ResultDecision;
  financials: ResultFinancials;
  investment_breakdown: InvestmentItem[];
  graphs: GraphsMap;
  drivers: ResultDriver[];
  reasoning: ResultReasoning;
}
