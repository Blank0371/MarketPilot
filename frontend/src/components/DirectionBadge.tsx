import { cn } from "@/lib/utils";
import type { DriverDirection } from "@/lib/types";

const styles: Record<DriverDirection, string> = {
  positive: "bg-decision-launch-soft text-decision-launch border-decision-launch/30",
  negative: "bg-decision-danger-soft text-decision-danger border-decision-danger/30",
  mixed: "bg-decision-adapt-soft text-decision-adapt-foreground border-decision-adapt/40",
};

export function DirectionBadge({ direction }: { direction: DriverDirection }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        styles[direction],
      )}
    >
      {direction}
    </span>
  );
}
