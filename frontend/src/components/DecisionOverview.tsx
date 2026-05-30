import { cn } from "@/lib/utils";
import { CheckCircle2, AlertTriangle, Clock, XCircle } from "lucide-react";
import type { DecisionLabel, ResultDecision } from "@/lib/types";

interface DecisionOverviewProps {
  decision: ResultDecision;
}

const styleMap: Record<
  DecisionLabel,
  { token: string; icon: React.ReactNode; subtitle: string }
> = {
  Launch: {
    token: "launch",
    icon: <CheckCircle2 className="h-5 w-5" />,
    subtitle: "Forecast supports a confident go-to-market.",
  },
  "Adapt concept": {
    token: "adapt",
    icon: <AlertTriangle className="h-5 w-5" />,
    subtitle: "Viable with targeted adjustments to the business model.",
  },
  Delay: {
    token: "delay",
    icon: <Clock className="h-5 w-5" />,
    subtitle: "Wait for stronger demand signals before committing.",
  },
  "Do not launch": {
    token: "danger",
    icon: <XCircle className="h-5 w-5" />,
    subtitle: "Forecast does not support a launch at these assumptions.",
  },
};

export function DecisionOverview({ decision }: DecisionOverviewProps) {
  const s = styleMap[decision.label];
  const cssVar = `var(--decision-${s.token})`;
  const softVar = `var(--decision-${s.token}-soft)`;

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-white/10 bg-card/60 p-6 shadow-[0_0_80px_-30px_var(--primary)] backdrop-blur sm:p-8"
      style={{
        backgroundImage: `radial-gradient(60% 100% at 0% 0%, ${softVar}, transparent 60%)`,
      }}
    >
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div className="space-y-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Decision recommendation
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-semibold shadow-[0_0_24px_-6px_currentColor]"
              style={{ backgroundColor: cssVar, color: "var(--background)" }}
            >
              {s.icon}
              {decision.label}
            </span>
            <span className="text-xs text-muted-foreground">{s.subtitle}</span>
          </div>
          <p className="max-w-xl text-base leading-relaxed text-foreground/85">
            {decision.summary}
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <StatTile
            label="Quality score"
            value={`${decision.quality_score}`}
            sub="/ 100"
            accent={cssVar}
          />
          <StatTile label="Risk level" value={decision.risk_level} accent="var(--decision-adapt)" />
          <StatTile
            label="Confidence"
            value={`${Math.round(decision.confidence * 100)}%`}
            accent="var(--primary)"
          />
        </div>
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-background/40 p-3.5 backdrop-blur">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p
        className={cn("mt-2 text-2xl font-semibold tabular-nums")}
        style={{ color: accent }}
      >
        {value}
        {sub && <span className="ml-0.5 text-xs text-muted-foreground">{sub}</span>}
      </p>
    </div>
  );
}
