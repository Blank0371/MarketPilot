import type {
  CalculationResult,
  EditableFieldGroup,
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
  headline: "Turn business ideas into forecast-driven launch decisions.",
  slogan: productSlogan,
  subheadline:
    "MarketPilot converts an unstructured business idea into editable assumptions, market signals, probabilistic forecasts, financial projections, and a clear go/no-go recommendation.",
  ctaLabel: "Start analysis",
};

export const trustFeatures: string[] = [
  "Editable assumptions",
  "Forecast drivers",
  "Financial projection",
  "Go / No-Go decision",
];

export const stepDefinitions: StepDefinition[] = [
  { id: 1, label: "Idea input", description: "Describe the concept" },
  { id: 2, label: "Review fields", description: "Edit assumptions" },
  { id: 3, label: "Results dashboard", description: "Decision cockpit" },
];

export const exampleChips: string[] = [
  "Wine store in Vienna",
  "Online delivery",
  "Premium café",
  "Urban convenience store",
  "Fitness studio",
];

export const pitchPlaceholder =
  "Example: I want to open a premium wine store in Vienna's 1st district with a focus on online delivery and corporate gift boxes.";

/**
 * Mock editable fields returned by the backend after extracting the pitch.
 * Grouped by category and fully generic — the Review step renders these
 * without hard-coding any field names.
 */
export const mockEditableFieldGroups: EditableFieldGroup[] = [
  {
    category: "Business",
    fields: [
      { key: "business_type", label: "Business type", type: "text", value: "Premium wine store", confidence: "High" },
      { key: "business_model", label: "Business model", type: "text", value: "Retail + tastings + online delivery" },
      {
        key: "pricing_position",
        label: "Pricing position",
        type: "select",
        value: "Premium",
        options: ["Budget", "Mid-market", "Premium", "Luxury"],
        confidence: "Medium",
      },
      { key: "sales_channels", label: "Sales channels", type: "tags", value: ["Physical retail", "Online delivery"] },
      {
        key: "target_customers",
        label: "Target customers",
        type: "tags",
        value: ["Tourists", "Locals", "Restaurants", "Corporate gifts"],
      },
    ],
  },
  {
    category: "Location",
    fields: [
      { key: "city", label: "City", type: "text", value: "Vienna", confidence: "High" },
      { key: "district", label: "District", type: "text", value: "1st district" },
      { key: "country", label: "Country", type: "text", value: "Austria" },
    ],
  },
  {
    category: "Forecast Context",
    fields: [
      {
        key: "forecast_target",
        label: "Forecast target",
        type: "text",
        value: "Tourism-driven premium retail demand",
        confidence: "Medium",
      },
      {
        key: "forecast_keywords",
        label: "Forecast keywords",
        type: "tags",
        value: [
          "Vienna tourism",
          "premium retail spending",
          "wine retail",
          "online delivery",
          "consumer spending",
          "seasonality",
          "rent pressure",
        ],
      },
      {
        key: "forecast_horizon_months",
        label: "Forecast horizon (months)",
        type: "number",
        value: 6,
      },
    ],
  },
  {
    category: "Financial Assumptions",
    fields: [
      { key: "initial_investment", label: "Initial investment", type: "currency", value: 120000 },
      { key: "monthly_rent", label: "Monthly rent", type: "currency", value: 8000 },
      { key: "staff_costs", label: "Staff costs (monthly)", type: "currency", value: 12000 },
      { key: "average_basket_size", label: "Average basket size", type: "currency", value: 42 },
      { key: "gross_margin", label: "Gross margin", type: "percentage", value: 35 },
    ],
  },
  {
    category: "Market Signals",
    fields: [
      { key: "competition_level", label: "Competition level", type: "percentage", value: 65, helper: "Predicted relative density" },
      { key: "tourism_index", label: "Tourism index", type: "percentage", value: 78 },
      {
        key: "market_signals",
        label: "Tracked market signals",
        type: "tags",
        value: ["Premium retail spending", "Tourism demand", "Rent pressure", "Seasonality"],
      },
    ],
  },
];

/**
 * Mock calculation result — matches the documented backend JSON shape.
 */
export const mockCalculationResult: CalculationResult = {
  decision: {
    label: "Adapt concept",
    quality_score: 72,
    risk_level: "Medium",
    confidence: 0.68,
    summary:
      "The concept has demand potential, but predicted rent pressure creates downside risk.",
  },
  financials: {
    expected_monthly_revenue: 42000,
    expected_monthly_costs: 37800,
    expected_monthly_profit: 4200,
    estimated_initial_investment: 120000,
    break_even_probability: 0.67,
    payback_period_months: 29,
  },
  investment_breakdown: [
    { category: "Initial inventory", amount: 45000 },
    { category: "Store setup", amount: 35000 },
    { category: "Launch marketing", amount: 15000 },
    { category: "Legal and licensing", amount: 5000 },
    { category: "Cash buffer", amount: 20000 },
  ],
  graphs: {
    demand_forecast: [
      { month: "2026-06", p10: 820, p50: 1040, p90: 1280 },
      { month: "2026-07", p10: 860, p50: 1090, p90: 1350 },
      { month: "2026-08", p10: 910, p50: 1160, p90: 1440 },
      { month: "2026-09", p10: 760, p50: 980, p90: 1210 },
      { month: "2026-10", p10: 700, p50: 930, p90: 1160 },
      { month: "2026-11", p10: 780, p50: 990, p90: 1240 },
    ],
    rent_forecast: [
      { month: "2026-06", p10: 7600, p50: 8200, p90: 9100 },
      { month: "2026-07", p10: 7700, p50: 8350, p90: 9300 },
      { month: "2026-08", p10: 7800, p50: 8500, p90: 9500 },
      { month: "2026-09", p10: 7900, p50: 8700, p90: 9800 },
      { month: "2026-10", p10: 8000, p50: 8900, p90: 10100 },
      { month: "2026-11", p10: 8100, p50: 9100, p90: 10400 },
    ],
    revenue_forecast: [
      { month: "2026-06", p10: 33000, p50: 42000, p90: 51000 },
      { month: "2026-07", p10: 34000, p50: 43500, p90: 53000 },
      { month: "2026-08", p10: 36000, p50: 46000, p90: 56000 },
      { month: "2026-09", p10: 31000, p50: 39500, p90: 49000 },
      { month: "2026-10", p10: 30000, p50: 38000, p90: 47000 },
      { month: "2026-11", p10: 32000, p50: 40500, p90: 50000 },
    ],
  },
  drivers: [
    {
      name: "Premium retail spending",
      importance: 0.78,
      direction: "positive",
      explanation: "Premium retail demand supports the concept.",
    },
    {
      name: "Rent pressure",
      importance: 0.73,
      direction: "negative",
      explanation: "Predicted rent pressure increases fixed cost risk.",
    },
    {
      name: "Tourism demand",
      importance: 0.71,
      direction: "positive",
      explanation: "Tourism demand increases upside potential.",
    },
    {
      name: "Seasonality",
      importance: 0.61,
      direction: "mixed",
      explanation: "Seasonality creates demand volatility.",
    },
  ],
  reasoning: {
    main_reason:
      "The concept has demand potential, but predicted rent pressure creates downside risk.",
    positive_factors: [
      "Premium retail demand supports the wine store concept.",
      "Online delivery expands customer reach.",
      "Tourism demand increases upside potential.",
    ],
    negative_factors: [
      "Predicted rent pressure increases fixed costs.",
      "Seasonality creates demand volatility.",
      "Competition density limits customer capture.",
    ],
    recommended_actions: [
      "Adapt the concept toward online delivery and corporate gift boxes.",
      "Avoid high-rent leases above the predicted threshold.",
      "Add tastings or B2B sales to improve margins.",
    ],
  },
};

/** Pretty labels for the graphs map keys. */
export const graphLabels: Record<string, string> = {
  demand_forecast: "Demand forecast",
  rent_forecast: "Rent price forecast",
  revenue_forecast: "Revenue forecast",
};
