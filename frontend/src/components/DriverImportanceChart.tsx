import type { Driver } from "@/lib/types";
import { DirectionBadge } from "./DirectionBadge";

interface DriverImportanceChartProps {
  drivers: Driver[];
}

const directionToVar: Record<Driver["direction"], string> = {
  positive: "var(--decision-launch)",
  negative: "var(--decision-danger)",
  mixed: "var(--decision-adapt)",
};

export function DriverImportanceChart({ drivers }: DriverImportanceChartProps) {
  return (
    <ul className="space-y-3">
      {drivers.map((d) => {
        const pct = Math.round(d.importance * 100);
        return (
          <li key={d.name} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{d.name}</span>
                <DirectionBadge direction={d.direction} />
              </div>
              <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                {pct}%
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, background: directionToVar[d.direction] }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
