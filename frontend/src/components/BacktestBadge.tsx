import { cn } from "@/lib/utils";
import { ShieldCheck } from "lucide-react";
import type { Backtest } from "@/lib/types";

interface BacktestBadgeProps {
  backtest: Backtest;
  className?: string;
}

const QUALITY_COLOR: Record<string, string> = {
  high: "text-decision-launch",
  "medium-high": "text-primary",
  medium: "text-decision-adapt",
  "medium-low": "text-decision-delay",
  low: "text-decision-danger",
};

export function BacktestBadge({ backtest, className }: BacktestBadgeProps) {
  const color = QUALITY_COLOR[backtest.quality.toLowerCase()] ?? "text-muted-foreground";
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-white/10 bg-background/40 px-3 py-1.5 text-xs backdrop-blur",
        className,
      )}
    >
      <ShieldCheck className={cn("h-3.5 w-3.5 shrink-0", color)} />
      <span className="text-muted-foreground">Forecast quality:</span>
      <span className={cn("font-semibold capitalize", color)}>{backtest.quality}</span>
      <span className="text-muted-foreground/60">·</span>
      <span className="text-muted-foreground">
        MAPE <span className="font-medium text-foreground/80">{backtest.mape}%</span>
      </span>
    </div>
  );
}
