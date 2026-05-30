import type { ReasoningItem } from "@/lib/types";
import { DirectionBadge } from "./DirectionBadge";

interface ReasoningPanelProps {
  items: ReasoningItem[];
}

export function ReasoningPanel({ items }: ReasoningPanelProps) {
  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li key={item.factor} className="border-l-2 border-border pl-4">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-foreground">{item.factor}</p>
            <DirectionBadge direction={item.impact} />
          </div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {item.explanation}
          </p>
        </li>
      ))}
    </ul>
  );
}
