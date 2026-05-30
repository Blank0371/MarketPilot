import type { AddedMarketFactor } from "@/lib/mockApi";
import { CheckCircle2, Loader2, XCircle, Tag } from "lucide-react";
import { cn } from "@/lib/utils";

interface AddedFactorListProps {
  factors: AddedMarketFactor[];
}

const STATUS_ICON: Record<AddedMarketFactor["status"], React.ReactNode> = {
  queued: <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin" />,
  running: <Loader2 className="h-3.5 w-3.5 text-primary animate-spin" />,
  added: <CheckCircle2 className="h-3.5 w-3.5 text-decision-launch" />,
  failed: <XCircle className="h-3.5 w-3.5 text-decision-danger" />,
};

const STATUS_LABEL: Record<AddedMarketFactor["status"], string> = {
  queued: "Queued",
  running: "Running forecast…",
  added: "Added",
  failed: "Failed",
};

export function AddedFactorList({ factors }: AddedFactorListProps) {
  if (!factors.length) return null;
  return (
    <ul className="space-y-2">
      {factors.map((f, i) => (
        <li
          key={i}
          className="rounded-xl border border-white/8 bg-background/40 px-4 py-3 space-y-2"
        >
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm text-foreground/90 leading-snug">{f.description}</p>
            <StatusBadge status={f.status} />
          </div>

          {f.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {f.keywords.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/8 px-2 py-0.5 text-[10px] font-medium text-primary"
                >
                  <Tag className="h-2.5 w-2.5" />
                  {kw}
                </span>
              ))}
            </div>
          )}

          {f.reason_for_update && (
            <p className="text-[11px] text-muted-foreground leading-snug border-t border-white/5 pt-2">
              {f.reason_for_update}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function StatusBadge({ status }: { status: AddedMarketFactor["status"] }) {
  const colorClass = cn(
    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold shrink-0",
    status === "added"
      ? "border-decision-launch/30 bg-decision-launch-soft text-decision-launch"
      : status === "failed"
      ? "border-decision-danger/30 bg-decision-danger-soft text-decision-danger"
      : "border-white/10 bg-secondary/40 text-muted-foreground",
  );
  return (
    <span className={colorClass}>
      {STATUS_ICON[status]}
      {STATUS_LABEL[status]}
    </span>
  );
}
