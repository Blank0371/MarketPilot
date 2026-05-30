import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DecisionOverview } from "./DecisionOverview";
import { FinancialProjection } from "./FinancialProjection";
import { ForecastChart } from "./ForecastChart";
import { DriverImportanceChart } from "./DriverImportanceChart";
import { InvestmentBreakdown } from "./InvestmentBreakdown";
import { ReasoningCard } from "./ReasoningCard";
import { BacktestBadge } from "./BacktestBadge";
import { WhatIfControl } from "./WhatIfControl";
import type { Report, WhatIfOverrides } from "@/lib/types";
import { recompute } from "@/lib/mockApi";
import { useState, useCallback } from "react";

interface ResultsDashboardProps {
  report: Report;
}

export function ResultsDashboard({ report: baseReport }: ResultsDashboardProps) {
  const [report, setReport] = useState<Report>(baseReport);

  const handleWhatIf = useCallback(
    (overrides: WhatIfOverrides) => {
      setReport(recompute(baseReport, overrides));
    },
    [baseReport],
  );

  return (
    <div className="space-y-6">
      {/* 1. Verdict — hero of the screen */}
      <DecisionOverview decision={report.decision} />

      {/* 2. Financial metrics */}
      <Section
        title="Financial projection"
        description="Estimated revenue, costs, and break-even outlook derived from the forecast."
      >
        <FinancialProjection financials={report.financials} />
      </Section>

      {/* 3. Forecast chart — history + forecast + confidence band */}
      <Section
        title="Demand forecast"
        description="Historical revenue signal and 6-month probabilistic forecast with confidence band."
        badge={<BacktestBadge backtest={report.backtest} />}
      >
        <Card className="border-white/10 bg-card/60 shadow-[0_0_40px_-24px_var(--primary)] backdrop-blur">
          <CardContent className="pt-6">
            <ForecastChart
              historical={report.graphs.historical_series}
              forecast={report.graphs.demand_forecast}
            />
          </CardContent>
        </Card>
      </Section>

      {/* 4. Drivers + Investment */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="border-white/10 bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base">Driver importance</CardTitle>
            <CardDescription>
              Relative weight of each signal — and how importance shifts across the
              forecast horizon.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <DriverImportanceChart drivers={report.drivers} />
            {report.drivers.some((d) => d.explanation) && (
              <ul className="space-y-2 border-t border-white/5 pt-3 text-xs text-muted-foreground">
                {report.drivers.map(
                  (d) =>
                    d.explanation && (
                      <li key={d.name}>
                        <span className="font-medium text-foreground/80">{d.name}:</span>{" "}
                        {d.explanation}
                      </li>
                    ),
                )}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base">Investment breakdown</CardTitle>
            <CardDescription>
              Estimated allocation of the initial investment across categories.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <InvestmentBreakdown items={report.investment_breakdown} />
          </CardContent>
        </Card>
      </div>

      {/* 5. Reasoning */}
      <Card className="border-white/10 bg-card/60 backdrop-blur">
        <CardHeader>
          <CardTitle className="text-base">Reasoning &amp; recommended moves</CardTitle>
          <CardDescription>
            Why the agent reached this decision — and what to do next.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ReasoningCard reason={report.reason} />
        </CardContent>
      </Card>

      {/* 6. What-if control */}
      <WhatIfControl onChange={handleWhatIf} />
    </div>
  );
}

function Section({
  title,
  description,
  badge,
  children,
}: {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground/90">{title}</h3>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}
