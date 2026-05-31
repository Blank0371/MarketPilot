/**
 * Show-case mock datasets for `Data mode: mock`.
 *
 * Each case is a full, internally-consistent `Report` (the shape the dashboard
 * renders — see types.ts and report_agent.py `_Report` for the backend mirror:
 * decision / financials(expected_revenue) / investment_breakdown(investment_cost) /
 * graphs / drivers / backtest / reason). `getResult` in mockApi.ts returns one of
 * these directly, so the mock dashboard looks exactly like a real successful run.
 *
 * Everything is DETERMINISTIC: the seasonal series come from a pure sine-based
 * generator (no Math.random, no Date.now), evaluated once at module load, so the
 * demo is byte-stable across renders.
 *
 * The graphs are built so history and forecast read as ONE continuous, smooth
 * line: `demand_forecast[0].mid === historical_series[last].value` exactly
 * (seamless junction — ForecastChart joins the lines there), the seasonality is a
 * smooth sinusoid (summer above winter), and the confidence band funnels out with
 * the forecast horizon (low < mid < high in every point).
 */
import type { Report, HistoricalPoint, ForecastBandPoint, Driver } from "./types";

export interface MockCase {
  id: string;
  /** Human label for the idea (used by example chips). */
  idea: string;
  /** Keyword matcher against the user's free-text idea. */
  match: RegExp;
  descriptions: string[];
  report: Report;
}

// ─── Deterministic smooth-series generator ─────────────────────────────────────

const Z_P90 = 1.2816; // standard-normal p10/p90 quantile → band half-width
/** Sentinel the dashboard renders as "—" (no payback; used when profit ≤ 0). */
export const NO_PAYBACK = 999;

interface SeriesSpec {
  level: number; // annual-average monthly revenue (EUR) — graph mean ≈ this
  amp: number; // seasonal amplitude (0 flat … ~0.6 strongly seasonal)
  trendPerMonth: number; // 1.0 = flat, >1 growth, <1 decline
  sigmaBase: number; // relative band half-width at the forecast start
  sigmaWiden: number; // extra half-width added per forecast month (the funnel)
  startYear: number;
  startMonth: number; // 1..12 — first historical month
  historyLen: number; // number of historical months (18–24)
  forecastLen: number; // number of forecast months (6)
}

function isoMonth(startYear: number, startMonth: number, offset: number): string {
  const idx = startYear * 12 + (startMonth - 1) + offset;
  const y = Math.floor(idx / 12);
  const m = (idx % 12) + 1;
  return `${y}-${String(m).padStart(2, "0")}-01`;
}

/** Smooth seasonal multiplier: peak in July (month 7), trough in January. */
function seasonal(calendarMonth: number, amp: number): number {
  return 1 + amp * Math.sin((2 * Math.PI * (calendarMonth - 4)) / 12);
}

function buildGraphs(s: SeriesSpec): {
  historical_series: HistoricalPoint[];
  demand_forecast: ForecastBandPoint[];
} {
  // Demand level at a given month-offset from the series start (continuous curve).
  const value = (offset: number): number => {
    const calMonth = ((s.startMonth - 1 + offset) % 12) + 1;
    return s.level * Math.pow(s.trendPerMonth, offset) * seasonal(calMonth, s.amp);
  };

  const historical_series: HistoricalPoint[] = [];
  for (let i = 0; i < s.historyLen; i++) {
    historical_series.push({
      month: isoMonth(s.startYear, s.startMonth, i),
      value: Math.round(value(i)),
    });
  }

  const demand_forecast: ForecastBandPoint[] = [];
  for (let k = 0; k < s.forecastLen; k++) {
    // mid follows the same curve but is anchored so forecast[0] === last history
    // point (k=0 → value(historyLen-1)). This makes the junction seamless and the
    // forecast a smooth continuation; the band funnels out with k.
    const mid = Math.round(value(s.historyLen - 1 + k));
    const sigma = s.sigmaBase + s.sigmaWiden * k;
    demand_forecast.push({
      month: isoMonth(s.startYear, s.startMonth, s.historyLen + k),
      low: Math.max(0, Math.round(mid * (1 - Z_P90 * sigma))),
      mid,
      high: Math.round(mid * (1 + Z_P90 * sigma)),
    });
  }

  return { historical_series, demand_forecast };
}

// All cases share a 24-month history ending Apr 2026 and a 6-month forecast
// (May–Oct 2026) — consecutive months, no gaps, no duplicates.
const HISTORY = { startYear: 2024, startMonth: 5, historyLen: 24, forecastLen: 6 };

/** Build a driver with a smoothly-decaying importance across the horizon. */
function driver(
  name: string,
  importance: number,
  direction: Driver["direction"],
  explanation: string,
  decay = 0.9,
): Driver {
  return {
    name,
    importance,
    direction,
    horizon: {
      month_1: importance,
      month_3: Math.round(importance * decay * 100) / 100,
      month_6: Math.round(importance * decay * decay * 100) / 100,
    },
    explanation,
  };
}

// ─── Case 1 — Ice cream shop (strongly seasonal, perishable) → "Adapt concept" ──

const iceCream: MockCase = {
  id: "icecream",
  idea: "Ice cream shop in Vienna's 1st district",
  match: /ice ?cream|gelato|frozen|dessert|sorbet/i,
  descriptions: [
    "Average monthly rent for a small retail unit in Vienna's 1st district",
    "Monthly consumer spending on ice cream and frozen desserts in Vienna",
    "Tourism visitor volume in Vienna's 1st district by month",
    "Seasonality index for ice cream and gelato sales in Central Europe",
    "Competition density for dessert and ice cream shops in the tourist corridor",
  ],
  report: {
    decision: {
      label: "Adapt concept",
      score: 64,
      risk_level: "High",
      confidence: 0.74,
      summary:
        "Strong summer tourism makes peak months very profitable, but deep winter seasonality against year-round 1st-district rent leaves a thin annual margin. Viable — if the off-season is managed.",
    },
    financials: {
      expected_monthly_revenue: 30000,
      expected_monthly_costs: 26500,
      expected_monthly_profit: 3500,
      estimated_initial_investment: 72000,
      break_even_probability: 0.58,
      payback_period_months: 21, // round(72000 / 3500)
    },
    graphs: buildGraphs({
      ...HISTORY,
      level: 30000,
      amp: 0.5,
      trendPerMonth: 1.003,
      sigmaBase: 0.06,
      sigmaWiden: 0.035,
    }),
    drivers: [
      driver(
        "Tourism Arrivals",
        0.84,
        "positive",
        "Vienna's 1st-district tourist volume is the primary demand driver — July and August are make-or-break.",
      ),
      driver(
        "Summer Temperature / Heatwaves",
        0.79,
        "positive",
        "Hot spells lift impulse demand; the peak season is weather-amplified.",
      ),
      driver(
        "Winter Seasonality",
        0.71,
        "negative",
        "Demand collapses Nov–Feb while fixed costs run year-round.",
      ),
      driver(
        "Disposable Income",
        0.55,
        "positive",
        "Vienna's high spending supports premium pricing.",
      ),
      driver(
        "Local Foot Traffic",
        0.5,
        "positive",
        "Steady passer-by demand underpins the shoulder months.",
      ),
    ],
    investment_breakdown: [
      { category: "Equipment (soft-serve, freezers, display)", amount: 24000 },
      { category: "Store fit-out & décor", amount: 20000 },
      { category: "Initial inventory & supplies", amount: 9000 },
      { category: "Launch marketing & activation", amount: 8000 },
      { category: "Cash buffer (winter reserve)", amount: 6000 },
      { category: "Legal, licensing & permits", amount: 5000 },
    ],
    reason: {
      main_reason:
        "The concept is forecast-viable in peak months (profit reaches €11,800 in a strong month), but €30,000 average revenue only clears €3,500 profit because winter demand collapses while fixed costs run year-round. The risk is cashflow, not concept.",
      positive_factors: [
        "Expected monthly profit of €3,500 on €30,000 revenue, rising to €11,800 in peak summer.",
        "Tourism Arrivals (importance 0.84) drives a predictable June–August demand surge.",
        "Vienna's high disposable income supports premium pricing and above-average baskets.",
      ],
      negative_factors: [
        "Only 58% of months across the year clear break-even.",
        "A weak month falls to a €4,800 loss as winter seasonality (importance 0.71) cuts demand.",
        "High risk: demand swings sharply between summer and winter.",
      ],
      recommended_actions: [
        "Add a winter line (hot drinks, pastries, seasonal desserts) to smooth the off-season.",
        "Negotiate a seasonal or turnover-linked rent to cut the winter fixed-cost burden.",
        "Pre-book summer capacity (events, catering) before the first peak season.",
      ],
    },
    backtest: { quality: "medium-high", mape: 13 },
  },
};

// ─── Case 2 — Boutique wine shop (niche, low growth) → "Delay" ──────────────────

const wine: MockCase = {
  id: "wine",
  idea: "Boutique wine shop in Vienna",
  match: /\bwine\b|vino|sommelier|vineyard|cellar/i,
  descriptions: [
    "Average monthly rent for a boutique retail unit in central Vienna",
    "Monthly consumer spending on premium and imported wine in Vienna",
    "Disposable income trend for Vienna's wine-buying demographic",
    "Seasonality index for wine retail in Austria (gifting & holidays)",
    "Density of competing wine merchants and supermarkets in the area",
  ],
  report: {
    decision: {
      label: "Delay",
      score: 41,
      risk_level: "Medium-high",
      confidence: 0.62,
      summary:
        "A niche, gift-driven demand profile yields only a razor-thin €900 monthly profit and a sub-50% break-even rate. The economics are too tight to commit capital now — wait for a better location or supplier terms.",
    },
    financials: {
      expected_monthly_revenue: 23000,
      expected_monthly_costs: 22100,
      expected_monthly_profit: 900,
      estimated_initial_investment: 34000,
      break_even_probability: 0.45,
      payback_period_months: 38, // round(34000 / 900)
    },
    graphs: buildGraphs({
      ...HISTORY,
      level: 23000,
      amp: 0.2,
      trendPerMonth: 0.999,
      sigmaBase: 0.09,
      sigmaWiden: 0.04,
    }),
    drivers: [
      driver(
        "Disposable Income",
        0.72,
        "positive",
        "Premium-wine demand tracks the spending power of central-Vienna buyers.",
      ),
      driver(
        "Tourism Arrivals",
        0.6,
        "positive",
        "Visitors add gift and souvenir-bottle purchases.",
      ),
      driver(
        "Consumer Price Index",
        0.55,
        "negative",
        "Inflation squeezes discretionary wine spend and import costs.",
      ),
      driver(
        "Alcohol Excise Tax",
        0.48,
        "negative",
        "Excise increases compress an already-thin margin.",
      ),
      driver(
        "Competitor Density",
        0.4,
        "negative",
        "Merchants and supermarkets cap pricing power.",
      ),
    ],
    investment_breakdown: [
      { category: "Store fit-out & shelving", amount: 13000 },
      { category: "Initial wine stock", amount: 10000 },
      { category: "Launch marketing & tastings", amount: 4000 },
      { category: "Legal, licensing & permits", amount: 4000 },
      { category: "Cash buffer", amount: 3000 },
    ],
    reason: {
      main_reason:
        "At €23,000 revenue against €22,100 costs, the shop earns just €900 per month and clears break-even in only 45% of months — a 38-month payback. The concept is sound but the current economics are too marginal to launch.",
      positive_factors: [
        "Disposable income (importance 0.72) supports premium-wine demand in central Vienna.",
        "A strong month reaches €7,400 profit, showing real upside if footfall improves.",
      ],
      negative_factors: [
        "Only 45% of months clear break-even and a weak month loses €5,600.",
        "Consumer Price Index and Alcohol Excise Tax both weigh negatively on margin.",
        "Dense competition from merchants and supermarkets limits pricing power.",
      ],
      recommended_actions: [
        "Delay until a higher-footfall location or better supplier terms lift the margin.",
        "Differentiate with tastings and events to raise the average basket above commodity wine.",
        "Re-run the forecast once a concrete lease and import-cost quote are available.",
      ],
    },
    backtest: { quality: "medium", mape: 18 },
  },
};

// ─── Case 3 — Specialty coffee & bakery (stable, low seasonality) → "Launch" ─────

const coffee: MockCase = {
  id: "coffee",
  idea: "Specialty coffee & bakery in Vienna",
  match: /coffee|caf[eé]|espresso|bakery|bakehouse|pastry|brunch|roastery/i,
  descriptions: [
    "Average monthly rent for a café-format retail unit in Vienna",
    "Daily commuter and office foot traffic near the location",
    "Monthly consumer spending on coffee and bakery goods in Vienna",
    "Office occupancy and return-to-work trend in the district",
    "Year-round demand stability for coffee versus seasonal products",
  ],
  report: {
    decision: {
      label: "Launch",
      score: 83,
      risk_level: "Low",
      confidence: 0.88,
      summary:
        "Stable, low-seasonality daily demand from commuters and offices delivers a healthy €8,000 monthly profit, an 82% break-even rate, and a 12-month payback. The forecast supports a confident go-to-market.",
    },
    financials: {
      expected_monthly_revenue: 38000,
      expected_monthly_costs: 30000,
      expected_monthly_profit: 8000,
      estimated_initial_investment: 95000,
      break_even_probability: 0.82,
      payback_period_months: 12, // round(95000 / 8000)
    },
    graphs: buildGraphs({
      ...HISTORY,
      level: 38000,
      amp: 0.08,
      trendPerMonth: 1.004,
      sigmaBase: 0.045,
      sigmaWiden: 0.025,
    }),
    drivers: [
      driver(
        "Local Foot Traffic",
        0.8,
        "positive",
        "Commuter and passer-by volume is the steady demand base.",
      ),
      driver(
        "Office Occupancy",
        0.62,
        "positive",
        "Nearby office return-to-work drives weekday mornings.",
      ),
      driver(
        "Disposable Income",
        0.58,
        "positive",
        "Supports a premium third-wave coffee position.",
      ),
      driver(
        "Consumer Price Index",
        0.5,
        "negative",
        "Coffee and dairy input inflation pressures margin.",
      ),
      driver("Tourism Arrivals", 0.44, "positive", "Adds weekend and seasonal upside."),
    ],
    investment_breakdown: [
      { category: "Store fit-out & seating", amount: 40000 },
      { category: "Equipment (espresso machine, oven)", amount: 22000 },
      { category: "Launch marketing & activation", amount: 12000 },
      { category: "Initial inventory & supplies", amount: 9000 },
      { category: "Cash buffer", amount: 6000 },
      { category: "Legal, licensing & permits", amount: 6000 },
    ],
    reason: {
      main_reason:
        "Daily coffee demand barely fluctuates with the seasons, so €38,000 revenue reliably clears €8,000 profit and 82% of months are above break-even — even a weak month stays positive at €2,400. The investment pays back in about 12 months.",
      positive_factors: [
        "Expected monthly profit of €8,000 on €38,000 revenue, with the downside still profitable at €2,400.",
        "Local foot traffic (importance 0.80) and office occupancy provide steady, repeatable demand.",
        "Low seasonality keeps the forecast band tight (7% backtest error → 88% confidence).",
      ],
      negative_factors: [
        "Consumer Price Index pressure on coffee and dairy inputs can compress margin.",
        "Returns depend on sustained office occupancy near the location.",
      ],
      recommended_actions: [
        "Lock in supplier pricing for coffee and dairy to protect the margin.",
        "Build a morning-commuter loyalty programme to defend the foot-traffic base.",
        "Add a light lunch line to lift the midday basket.",
      ],
    },
    backtest: { quality: "high", mape: 7 },
  },
};

// ─── Case 4 — Luxury watch boutique (high capital, niche) → "Do not launch" ──────

const luxury: MockCase = {
  id: "luxury",
  idea: "Luxury watch boutique in Vienna",
  match: /luxury|watch|jewel|designer|handbag|couture|high-end|boutique fashion/i,
  descriptions: [
    "Average monthly rent for a prestige retail unit on a premium Vienna street",
    "Consumer confidence and high-net-worth spending trend in Austria",
    "Import and inventory carrying costs for high-value timepieces",
    "Density of competing luxury and authorized-dealer boutiques",
    "Tourism arrivals of high-spending international visitors",
  ],
  report: {
    decision: {
      label: "Do not launch",
      score: 19,
      risk_level: "High",
      confidence: 0.57,
      summary:
        "Very high fixed costs and €180,000 tied up in slow-moving, high-value stock meet soft, confidence-sensitive demand. The model projects a €4,500 monthly loss with only a 21% break-even rate — the forecast does not support a launch.",
    },
    financials: {
      expected_monthly_revenue: 21000,
      expected_monthly_costs: 25500,
      expected_monthly_profit: -4500,
      estimated_initial_investment: 180000,
      break_even_probability: 0.21,
      payback_period_months: NO_PAYBACK, // loss → no payback (rendered as "—")
    },
    graphs: buildGraphs({
      ...HISTORY,
      level: 21000,
      amp: 0.15,
      trendPerMonth: 0.995,
      sigmaBase: 0.12,
      sigmaWiden: 0.05,
    }),
    drivers: [
      driver(
        "Consumer Confidence",
        0.78,
        "negative",
        "Luxury demand is highly sensitive to confidence shocks.",
      ),
      driver(
        "Disposable Income",
        0.66,
        "positive",
        "High-net-worth spending is a genuine tailwind.",
      ),
      driver(
        "Competitor Density",
        0.6,
        "negative",
        "Authorized dealers and established houses dominate.",
      ),
      driver(
        "Import & Inventory Costs",
        0.55,
        "negative",
        "High-value stock carries heavy financing and insurance cost.",
      ),
      driver(
        "Tourism Arrivals",
        0.5,
        "positive",
        "International visitors provide episodic high-ticket sales.",
      ),
    ],
    investment_breakdown: [
      { category: "Prestige store fit-out & security", amount: 85000 },
      { category: "Initial high-value inventory", amount: 45000 },
      { category: "Launch marketing & PR", amount: 25000 },
      { category: "Cash buffer", amount: 13000 },
      { category: "Legal, licensing & permits", amount: 12000 },
    ],
    reason: {
      main_reason:
        "At €21,000 revenue against €25,500 costs, the boutique loses €4,500 every month and clears break-even in only 21% of months; a weak month loses €14,500. With €180,000 of capital at risk and no payback, the forecast does not support launching.",
      positive_factors: [
        "A strong month can reach €5,500 profit when high-spending tourism peaks.",
        "Disposable income (importance 0.66) remains a genuine demand tailwind.",
      ],
      negative_factors: [
        "Projected monthly loss of €4,500, with a €14,500 downside in a weak month.",
        "Only 21% of months clear break-even — consumer confidence (importance 0.78) is a strong negative driver.",
        "€180,000 is tied up in slow-moving, high-value stock with high carrying costs.",
      ],
      recommended_actions: [
        "Do not launch the standalone boutique at these economics.",
        "Test demand via a concession or pop-up before committing prestige-retail capital.",
        "Reduce capital intensity by consigning inventory instead of buying it outright.",
      ],
    },
    backtest: { quality: "medium", mape: 24 },
  },
};

// ─── Registry + selection ───────────────────────────────────────────────────────

export const MOCK_CASES: MockCase[] = [iceCream, coffee, wine, luxury];

export const DEFAULT_MOCK_CASE_ID = "icecream";

/** Pick the show-case whose keywords match the free-text idea; default = ice cream. */
export function pickMockCaseId(idea: string): string {
  const text = (idea || "").toLowerCase();
  // wine before luxury so "boutique wine shop" → wine, not luxury.
  for (const c of [iceCream, coffee, wine, luxury]) {
    if (c.match.test(text)) return c.id;
  }
  return DEFAULT_MOCK_CASE_ID;
}

export function getMockCase(id: string): MockCase {
  return MOCK_CASES.find((c) => c.id === id) ?? iceCream;
}
