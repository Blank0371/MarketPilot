import type { Report } from "@/lib/types";

interface FinancialProjectionProps {
  financials: Report["financials"];
}

function fmtEUR(n: number): string {
  const sign = n < 0 ? "-" : "";
  return `${sign}€${Math.abs(n).toLocaleString("en-US")}`;
}

interface Cell {
  label: string;
  value: string;
  tone?: "positive" | "negative" | "primary" | "neutral";
}

export function FinancialProjection({ financials }: FinancialProjectionProps) {
  const cells: Cell[] = [
    {
      label: "Expected monthly revenue",
      value: fmtEUR(financials.expected_monthly_revenue),
      tone: "primary",
    },
    {
      label: "Expected monthly costs",
      value: fmtEUR(financials.expected_monthly_costs),
      tone: "neutral",
    },
    {
      label: "Expected monthly profit",
      value: fmtEUR(financials.expected_monthly_profit),
      tone: financials.expected_monthly_profit >= 0 ? "positive" : "negative",
    },
    {
      label: "Initial investment",
      value: fmtEUR(financials.estimated_initial_investment),
      tone: "neutral",
    },
    {
      label: "Break-even probability",
      value: `${Math.round(financials.break_even_probability * 100)}%`,
      tone: "primary",
    },
    {
      label: "Payback period",
      value: financials.payback_period_months >= 999 ? "—" : `${financials.payback_period_months} mo`,
      tone: "neutral",
    },
  ];

  const toneColor: Record<NonNullable<Cell["tone"]>, string> = {
    primary: "var(--primary)",
    positive: "var(--decision-launch)",
    negative: "var(--decision-danger)",
    neutral: "var(--foreground)",
  };

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {cells.map((c) => (
        <div
          key={c.label}
          className="group relative overflow-hidden rounded-xl border border-white/10 bg-card/60 p-4 backdrop-blur transition-colors hover:border-white/20"
          style={{
            borderTop: `2px solid ${toneColor[c.tone ?? "neutral"]}`,
            boxShadow: `inset 0 2px 12px -6px ${toneColor[c.tone ?? "neutral"]}40`,
          }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {c.label}
          </p>
          <p
            className="mt-2 text-xl font-semibold tabular-nums transition-all"
            style={{ color: toneColor[c.tone ?? "neutral"] }}
          >
            {c.value}
          </p>
        </div>
      ))}
    </div>
  );
}
