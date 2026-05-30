import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/lib/types";

const styles: Record<ConfidenceLevel, string> = {
  High: "bg-decision-launch-soft text-decision-launch border-decision-launch/30",
  Medium: "bg-decision-adapt-soft text-decision-adapt-foreground border-decision-adapt/40",
  Low: "bg-decision-danger-soft text-decision-danger border-decision-danger/30",
};

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        styles[level],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {level}
    </span>
  );
}
