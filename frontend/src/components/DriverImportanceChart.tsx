import type { Driver } from "@/lib/types";
import { DirectionBadge } from "./DirectionBadge";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

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
    <ul className="space-y-5">
      {drivers.map((d) => {
        const pct = Math.round(d.importance * 100);
        const horizonShift = getHorizonShift(d.horizon);

        return (
          <li key={d.name} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-foreground">{d.name}</span>
                <DirectionBadge direction={d.direction} />
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {horizonShift && (
                  <HorizonShiftBadge shift={horizonShift} />
                )}
                <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                  {pct}%
                </span>
              </div>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${pct}%`, background: directionToVar[d.direction] }}
              />
            </div>
            {/* Horizon comparison bar (if data present) */}
            {horizonShift && (
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <span>Now</span>
                <div className="flex-1 h-0.5 rounded bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded transition-all"
                    style={{
                      width: `${Math.round(horizonShift.m1 * 100)}%`,
                      background: directionToVar[d.direction],
                      opacity: 0.9,
                    }}
                  />
                </div>
                <span className="tabular-nums">{Math.round(horizonShift.m1 * 100)}%</span>
                <span className="text-muted-foreground/40">→</span>
                <span className="tabular-nums">{Math.round(horizonShift.m6 * 100)}%</span>
                <div className="flex-1 h-0.5 rounded bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded transition-all"
                    style={{
                      width: `${Math.round(horizonShift.m6 * 100)}%`,
                      background: directionToVar[d.direction],
                      opacity: 0.5,
                    }}
                  />
                </div>
                <span>Month 6</span>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

interface HorizonShift {
  m1: number;
  m6: number;
  delta: number;
}

function getHorizonShift(horizon?: Driver["horizon"]): HorizonShift | null {
  if (!horizon) return null;
  const m1 = horizon["month_1"];
  const m6 = horizon["month_6"];
  if (m1 == null || m6 == null) return null;
  return { m1, m6, delta: m6 - m1 };
}

function HorizonShiftBadge({ shift }: { shift: HorizonShift }) {
  const pctChange = Math.round(Math.abs(shift.delta) * 100);
  if (pctChange < 3) {
    return (
      <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground/60">
        <Minus className="h-2.5 w-2.5" />
        stable
      </span>
    );
  }
  const isUp = shift.delta > 0;
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] font-medium"
      style={{ color: isUp ? "var(--decision-launch)" : "var(--decision-danger)" }}
    >
      {isUp ? (
        <TrendingUp className="h-2.5 w-2.5" />
      ) : (
        <TrendingDown className="h-2.5 w-2.5" />
      )}
      {pctChange}pp at 6mo
    </span>
  );
}
