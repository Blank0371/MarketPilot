import type { ComparisonSummary } from "@/lib/types";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface ComparisonCardProps {
  label: "original" | "adjusted";
  summary: ComparisonSummary;
  baseline?: ComparisonSummary;
}

const DECISION_COLOR: Record<string, string> = {
  Launch: "var(--decision-launch)",
  "Adapt concept": "var(--decision-adapt)",
  Delay: "var(--decision-delay)",
  "Do not launch": "var(--decision-danger)",
};

const DECISION_SOFT: Record<string, string> = {
  Launch: "var(--decision-launch-soft)",
  "Adapt concept": "var(--decision-adapt-soft)",
  Delay: "var(--decision-delay-soft)",
  "Do not launch": "var(--decision-danger-soft)",
};

export function ComparisonCard({ label, summary, baseline }: ComparisonCardProps) {
  const isAdjusted = label === "adjusted";
  const decisionColor = DECISION_COLOR[summary.decision] ?? "var(--primary)";
  const decisionSoft = DECISION_SOFT[summary.decision] ?? "transparent";

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur"
      style={{
        backgroundImage: isAdjusted
          ? `radial-gradient(70% 80% at 0% 0%, ${decisionSoft}, transparent 60%)`
          : undefined,
      }}
    >
      {/* Card header */}
      <div className="mb-4 flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
          {isAdjusted ? "Adjusted" : "Original"}
        </span>
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-all"
          style={{ backgroundColor: decisionColor, color: "var(--background)" }}
        >
          {summary.decision}
        </span>
      </div>

      {/* Metrics */}
      <ul className="space-y-3">
        <MetricRow
          label="Expected monthly revenue"
          value={fmtEUR(summary.expected_monthly_revenue)}
          delta={
            isAdjusted && baseline
              ? computeDelta(
                  baseline.expected_monthly_revenue,
                  summary.expected_monthly_revenue,
                  "eur",
                  true,
                )
              : null
          }
        />
        <MetricRow
          label="Expected monthly profit"
          value={fmtEUR(summary.expected_monthly_profit)}
          delta={
            isAdjusted && baseline
              ? computeDelta(
                  baseline.expected_monthly_profit,
                  summary.expected_monthly_profit,
                  "eur",
                  true,
                )
              : null
          }
        />
        <MetricRow
          label="Break-even probability"
          value={`${Math.round(summary.break_even_probability * 100)}%`}
          delta={
            isAdjusted && baseline
              ? computeDelta(
                  baseline.break_even_probability,
                  summary.break_even_probability,
                  "pp",
                  true,
                )
              : null
          }
        />
        <MetricRow
          label="Risk level"
          value={summary.risk_level}
          delta={
            isAdjusted && baseline
              ? riskDelta(baseline.risk_level, summary.risk_level)
              : null
          }
        />
      </ul>
    </div>
  );
}

// ─── Row helpers ─────────────────────────────────────────────────────────────

interface Delta {
  text: string;
  direction: "up" | "down" | "same";
  isGood: boolean;
}

function MetricRow({
  label,
  value,
  delta,
}: {
  label: string;
  value: string;
  delta: Delta | null;
}) {
  return (
    <li className="space-y-0.5">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
        {label}
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-base font-semibold text-foreground tabular-nums">{value}</span>
        {delta && delta.direction !== "same" && (
          <DeltaBadge delta={delta} />
        )}
      </div>
    </li>
  );
}

function DeltaBadge({ delta }: { delta: Delta }) {
  const color = delta.isGood
    ? "var(--decision-launch)"
    : "var(--decision-danger)";
  const Icon = delta.direction === "up" ? TrendingUp : TrendingDown;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
      )}
      style={{
        background: `color-mix(in oklab, ${color} 18%, transparent)`,
        color,
      }}
    >
      <Icon className="h-2.5 w-2.5" />
      {delta.text}
    </span>
  );
}

// ─── Delta calculations ───────────────────────────────────────────────────────

function computeDelta(
  oldVal: number,
  newVal: number,
  format: "eur" | "pp",
  positiveIsGood: boolean,
): Delta {
  const diff = newVal - oldVal;
  if (Math.abs(diff) < 0.001) return { text: "–", direction: "same", isGood: true };

  let text: string;
  if (format === "eur") {
    const sign = diff > 0 ? "+" : "−";
    text = `${sign}€${Math.abs(Math.round(diff)).toLocaleString("en-US")}`;
  } else {
    // pp = percentage points
    const ppDiff = Math.round((newVal - oldVal) * 100);
    const sign = ppDiff > 0 ? "+" : "−";
    text = `${sign}${Math.abs(ppDiff)}pp`;
  }

  return {
    text,
    direction: diff > 0 ? "up" : "down",
    isGood: positiveIsGood ? diff > 0 : diff < 0,
  };
}

const RISK_ORDER = ["Low", "Medium-low", "Medium", "Medium-high", "High"];

function riskDelta(oldRisk: string, newRisk: string): Delta {
  const oldIdx = RISK_ORDER.indexOf(oldRisk);
  const newIdx = RISK_ORDER.indexOf(newRisk);
  if (oldIdx === newIdx || oldIdx === -1 || newIdx === -1)
    return { text: "–", direction: "same", isGood: true };
  const improved = newIdx < oldIdx;
  return {
    text: newRisk,
    direction: improved ? "down" : "up",
    isGood: improved,
  };
}

function fmtEUR(n: number): string {
  const sign = n < 0 ? "−" : "";
  return `${sign}€${Math.abs(Math.round(n)).toLocaleString("en-US")}`;
}
