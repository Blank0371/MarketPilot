import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DecisionOverview } from "./DecisionOverview";
import { FinancialProjection } from "./FinancialProjection";
import { ForecastGraphs } from "./ForecastGraphs";
import { DriverImportanceChart } from "./DriverImportanceChart";
import { InvestmentBreakdown } from "./InvestmentBreakdown";
import { ReasoningCard } from "./ReasoningCard";
import type { CalculationResult } from "@/lib/types";

interface ResultsDashboardProps {
  result: CalculationResult;
  graphLabels?: Record<string, string>;
}

export function ResultsDashboard({ result, graphLabels }: ResultsDashboardProps) {
  return (
    <div className="space-y-6">
      <DecisionOverview decision={result.decision} />

      <Section
        title="Financial projection"
        description="Estimated revenue, costs, and break-even outlook from the calculation."
      >
        <FinancialProjection financials={result.financials} />
      </Section>

      <Section
        title="Forecast graphs"
        description="Probabilistic forecasts (P10 / P50 / P90) for every series returned by the backend."
      >
        <ForecastGraphs graphs={result.graphs} labels={graphLabels} />
      </Section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="border-white/10 bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base">Driver importance</CardTitle>
            <CardDescription>
              Relative weight of the factors shaping the recommendation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <DriverImportanceChart
              drivers={result.drivers.map((d) => ({
                name: d.name,
                importance: d.importance,
                direction: d.direction,
              }))}
            />
            {result.drivers.some((d) => d.explanation) && (
              <ul className="space-y-2 border-t border-white/5 pt-3 text-xs text-muted-foreground">
                {result.drivers.map(
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
            <InvestmentBreakdown items={result.investment_breakdown} />
          </CardContent>
        </Card>
      </div>

      <Card className="border-white/10 bg-card/60 backdrop-blur">
        <CardHeader>
          <CardTitle className="text-base">Reasoning &amp; recommended actions</CardTitle>
          <CardDescription>
            Why the agent reached this decision and what to do next.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ReasoningCard reasoning={result.reasoning} />
        </CardContent>
      </Card>
    </div>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-foreground/90">{title}</h3>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}
