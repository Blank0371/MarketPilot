import type {
  AllowedOverride,
  HistoricalPoint,
  ForecastBandPoint,
  Report,
  NavLink,
  StepDefinition,
} from "./types";

export const productName = "MarketPilot";
export const productSlogan = "Navigate uncertainty before you launch.";

export const navLinks: NavLink[] = [
  { label: "Product", href: "#product" },
  { label: "Flow", href: "#how-it-works" },
  { label: "Demo", href: "#demo" },
];

export const heroCopy = {
  headline: "Forecast first. Launch second.",
  slogan: productSlogan,
  subheadline:
    "Turn a raw business idea into editable market signals, probabilistic revenue forecasts, and a go/no-go decision — with reasoning you can see and assumptions you can change.",
  ctaLabel: "Analyze my idea",
};

export const trustFeatures: string[] = [
  "Market signal extraction",
  "Probabilistic forecasts",
  "Financial projection",
  "Live what-if sensitivity",
];

export const stepDefinitions: StepDefinition[] = [
  { id: 1, label: "Idea input", description: "Describe your concept" },
  { id: 2, label: "Confirm factors", description: "Review & refine drivers" },
  { id: 3, label: "Decision cockpit", description: "Forecast-driven verdict" },
];

// Each chip maps to a prepared show-case in mockCases.ts (mock data mode).
export const exampleChips: string[] = [
  "Ice cream shop in Vienna's 1st district",
  "Specialty coffee & bakery in Vienna",
  "Boutique wine shop in Vienna",
  "Luxury watch boutique in Vienna",
  "Urban gelato kiosk",
];

export const pitchPlaceholder =
  "Example: I want to open a premium ice cream shop in Vienna's 1st district focused on summer tourism and seasonal specials.";

export const mockDescriptions: string[] = [
  "Average monthly rent for small retail units in Vienna's 1st district",
  "Monthly consumer spending on ice cream and frozen desserts in Vienna",
  "Tourism visitor volume in Vienna's 1st district by month",
  "Seasonality index for ice cream and gelato sales in Central Europe",
  "Competition density for dessert and ice cream shops in Vienna's 1st district",
];

// ─── Economic constants (aligned with allowedOverrides base values) ───────────

export const ECONOMICS = {
  base_revenue: 24000, // EUR/month — from mockReport
  base_basket_size: 42, // EUR — from allowedOverrides
  base_opening_days: 22, // days/month — from allowedOverrides
  staff_cost_per_employee: 2500, // EUR/month per non-founder employee
  fixed_overhead: 3500, // EUR/month (rent + utilities + misc)
  /** Derived: base_revenue / (base_basket × base_days) */
  daily_customers: 24000 / (42 * 22), // ≈ 26.0
};

// ─── Allowed overrides (rendered dynamically by WhatIfSensitivity) ─────────────

export const allowedOverrides: AllowedOverride[] = [
  {
    id: "average_basket_size",
    label: "Average basket size",
    type: "currency",
    unit: "EUR",
    base_value: 42,
    min: 20,
    max: 120,
    description: "Expected average customer spend per purchase.",
  },
  {
    id: "gross_margin",
    label: "Gross margin",
    type: "percentage",
    base_value: 0.35,
    min: 0.15,
    max: 0.7,
    description: "Expected margin after product purchasing costs.",
  },
  {
    id: "staffing_level",
    label: "Staffing level",
    type: "number",
    unit: "employees",
    base_value: 1,
    min: 0,
    max: 6,
    description: "Number of planned employees besides the founder.",
  },
  {
    id: "opening_days_per_month",
    label: "Opening days per month",
    type: "number",
    unit: "days",
    base_value: 22,
    min: 10,
    max: 30,
    description: "Number of days the business operates per month.",
  },
  {
    id: "initial_investment_budget",
    label: "Initial investment budget",
    type: "currency",
    unit: "EUR",
    base_value: 120000,
    min: 20000,
    max: 300000,
    description: "Available budget for launch, setup, inventory, and initial runway.",
  },
  {
    id: "product_price_level",
    label: "Product price level",
    type: "select",
    base_value: "premium",
    options: ["budget", "mid-market", "premium", "luxury"],
    description: "Overall pricing position of the business concept.",
  },
];

// ─── Historical series (Jan 2024 – Apr 2026, 28 months) ───────────────────────

export const mockHistoricalSeries: HistoricalPoint[] = [
  { month: "Jan '24", value: 3200 },
  { month: "Feb '24", value: 3900 },
  { month: "Mar '24", value: 8500 },
  { month: "Apr '24", value: 15200 },
  { month: "May '24", value: 21000 },
  { month: "Jun '24", value: 28000 },
  { month: "Jul '24", value: 34500 },
  { month: "Aug '24", value: 32000 },
  { month: "Sep '24", value: 19500 },
  { month: "Oct '24", value: 11000 },
  { month: "Nov '24", value: 5200 },
  { month: "Dec '24", value: 7800 },
  { month: "Jan '25", value: 3400 },
  { month: "Feb '25", value: 4100 },
  { month: "Mar '25", value: 9200 },
  { month: "Apr '25", value: 16000 },
  { month: "May '25", value: 22500 },
  { month: "Jun '25", value: 29500 },
  { month: "Jul '25", value: 36000 },
  { month: "Aug '25", value: 33500 },
  { month: "Sep '25", value: 20500 },
  { month: "Oct '25", value: 12000 },
  { month: "Nov '25", value: 5500 },
  { month: "Dec '25", value: 8200 },
  { month: "Jan '26", value: 3600 },
  { month: "Feb '26", value: 4300 },
  { month: "Mar '26", value: 9800 },
  { month: "Apr '26", value: 17000 },
];

export const mockDemandForecast: ForecastBandPoint[] = [
  { month: "May '26", low: 19000, mid: 24800, high: 33000 },
  { month: "Jun '26", low: 24500, mid: 32000, high: 42000 },
  { month: "Jul '26", low: 29000, mid: 37500, high: 48500 },
  { month: "Aug '26", low: 27000, mid: 35500, high: 46500 },
  { month: "Sep '26", low: 14000, mid: 21000, high: 29000 },
  { month: "Oct '26", low: 8000, mid: 12500, high: 18000 },
];

// ─── Full mock report ─────────────────────────────────────────────────────────

export const mockReport: Report = {
  decision: {
    label: "Adapt concept",
    score: 67,
    risk_level: "Medium",
    confidence: 0.71,
    summary:
      "Strong summer tourism demand powers the upside, but winter dead seasons and 1st-district rent pressure create meaningful downside risk. The concept works — but only if the off-season is managed aggressively.",
  },
  financials: {
    expected_monthly_revenue: 24000,
    expected_monthly_costs: 21600,
    expected_monthly_profit: 2400,
    estimated_initial_investment: 95000,
    break_even_probability: 0.63,
    payback_period_months: 40,
  },
  graphs: {
    historical_series: mockHistoricalSeries,
    demand_forecast: mockDemandForecast,
  },
  drivers: [
    {
      name: "Summer tourism",
      importance: 0.84,
      direction: "positive",
      horizon: { month_1: 0.84, month_3: 0.79, month_6: 0.52 },
      explanation:
        "Vienna's 1st-district tourist volume is the primary demand driver — peak July and August are make-or-break months.",
    },
    {
      name: "Seasonality",
      importance: 0.77,
      direction: "mixed",
      horizon: { month_1: 0.65, month_3: 0.82, month_6: 0.77 },
      explanation:
        "Demand swings 10× between peak summer and deep winter — managing cash flow across this cycle is the core operational challenge.",
    },
    {
      name: "Rent pressure",
      importance: 0.62,
      direction: "negative",
      horizon: { month_1: 0.58, month_3: 0.62, month_6: 0.67 },
      explanation:
        "1st-district commercial rents are forecast to rise. Fixed-cost base increases while winter revenue stays flat.",
    },
    {
      name: "Competition density",
      importance: 0.51,
      direction: "negative",
      horizon: { month_1: 0.49, month_3: 0.53, month_6: 0.55 },
      explanation:
        "The tourist corridor supports multiple players, but differentiation is critical to avoid price competition.",
    },
    {
      name: "Consumer spending",
      importance: 0.48,
      direction: "positive",
      horizon: { month_1: 0.52, month_3: 0.47, month_6: 0.43 },
      explanation:
        "Vienna's high spending index supports premium pricing and above-average basket sizes.",
    },
  ],
  investment_breakdown: [
    { category: "Equipment (soft-serve, display)", amount: 30000 },
    { category: "Store fit-out & décor", amount: 25000 },
    { category: "Launch marketing & activation", amount: 10000 },
    { category: "Initial inventory & supplies", amount: 8000 },
    { category: "Legal, licensing & permits", amount: 7000 },
    { category: "Cash buffer (winter reserve)", amount: 15000 },
  ],
  reason: {
    main_reason:
      "The concept is forecast-viable in peak months, but the annual average is pulled down by winter dead seasons. The risk is cashflow, not concept.",
    positive_factors: [
      "Summer tourism creates a highly predictable demand surge from June through August.",
      "Vienna's high consumer spending supports premium pricing and €8–12 average baskets.",
      "Seasonal specials and event catering can add non-weather-dependent revenue.",
    ],
    negative_factors: [
      "Winter revenue (Jan–Feb) covers less than 25% of fixed monthly costs.",
      "1st-district rent is projected to increase 4–6% annually over the forecast horizon.",
      "Heavy concentration of dessert options in the tourist corridor limits pricing power.",
    ],
    recommended_actions: [
      "Negotiate a seasonal lease to avoid paying peak rent through the winter dead period.",
      "Launch a hot drinks and winter specials menu from October to offset demand seasonality.",
      "Pre-build summer capacity (event boxes, catering partnerships) before the first peak season.",
    ],
  },
  backtest: {
    quality: "medium-high",
    mape: 11.3,
  },
};
