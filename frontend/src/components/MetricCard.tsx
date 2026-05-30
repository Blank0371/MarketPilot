import { cn } from "@/lib/utils";

export type MetricTone = "neutral" | "positive" | "negative" | "warning" | "primary";

interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  tone?: MetricTone;
}

const toneClasses: Record<MetricTone, string> = {
  neutral: "text-foreground",
  primary: "text-primary",
  positive: "text-decision-launch",
  warning: "text-decision-adapt-foreground",
  negative: "text-decision-danger",
};

export function MetricCard({ label, value, sublabel, tone = "neutral" }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-2 text-2xl font-semibold tabular-nums", toneClasses[tone])}>
        {value}
      </p>
      {sublabel && <p className="mt-1 text-xs text-muted-foreground">{sublabel}</p>}
    </div>
  );
}
