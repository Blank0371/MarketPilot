import { Check, X, Lightbulb } from "lucide-react";
import type { Report } from "@/lib/types";

interface ReasoningCardProps {
  reason: Report["reason"];
}

export function ReasoningCard({ reason }: ReasoningCardProps) {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-white/10 bg-background/50 p-5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Core reason
        </p>
        <p className="mt-2.5 text-sm leading-relaxed text-foreground/90">{reason.main_reason}</p>
      </div>

      <FactorList
        title="What works"
        items={reason.positive_factors}
        color="var(--decision-launch)"
        Icon={Check}
      />
      <FactorList
        title="What doesn't"
        items={reason.negative_factors}
        color="var(--decision-danger)"
        Icon={X}
      />
      <FactorList
        title="Recommended moves"
        items={reason.recommended_actions}
        color="var(--primary)"
        Icon={Lightbulb}
      />
    </div>
  );
}

function FactorList({
  title,
  items,
  color,
  Icon,
}: {
  title: string;
  items: string[];
  color: string;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  if (!items.length) return null;
  return (
    <div>
      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {title}
      </p>
      <ul className="space-y-2">
        {items.map((it) => (
          <li
            key={it}
            className="flex items-start gap-3 rounded-lg border border-white/8 bg-background/40 px-3.5 py-3 text-sm text-foreground/90"
          >
            <span
              className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full"
              style={{ background: `color-mix(in oklab, ${color} 25%, transparent)`, color }}
            >
              <Icon className="h-2.5 w-2.5" />
            </span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
