import type { ChangedAssumption } from "@/lib/types";
import { ArrowRight } from "lucide-react";

interface ChangedAssumptionsListProps {
  changes: ChangedAssumption[];
}

export function ChangedAssumptionsList({ changes }: ChangedAssumptionsListProps) {
  if (!changes.length) return null;

  return (
    <div>
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
        Changed assumptions
      </p>
      <ul className="space-y-1.5">
        {changes.map((c, i) => (
          <li
            key={i}
            className="flex flex-wrap items-center gap-1.5 rounded-lg border border-white/5 bg-background/30 px-3 py-2 text-xs"
          >
            <span className="font-medium text-foreground/80">{c.label}</span>
            <span className="text-muted-foreground/50 text-[10px]">·</span>
            <span className="tabular-nums text-muted-foreground">{formatVal(c.old, c.unit)}</span>
            <ArrowRight className="h-3 w-3 text-muted-foreground/50 shrink-0" />
            <span
              className="tabular-nums font-semibold"
              style={{ color: "var(--primary)" }}
            >
              {formatVal(c.new, c.unit)}
            </span>
            {c.unit && (
              <span className="text-muted-foreground/60">{c.unit}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatVal(v: number | string, unit?: string): string {
  if (typeof v === "string") return v;
  if (unit === "EUR") return `€${Math.round(v).toLocaleString("en-US")}`;
  if (unit === "%") return `${Math.round(v * 100)}%`;
  return String(v);
}
