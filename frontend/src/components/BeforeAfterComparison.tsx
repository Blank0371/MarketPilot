import type { ComparisonResult } from "@/lib/types";
import { ComparisonCard } from "./ComparisonCard";
import { ChangedAssumptionsList } from "./ChangedAssumptionsList";
import { GitCompare, Tag } from "lucide-react";

interface BeforeAfterComparisonProps {
  comparison: ComparisonResult;
}

export function BeforeAfterComparison({ comparison }: BeforeAfterComparisonProps) {
  const { baseline, adjusted, changed_assumptions, added_factor, impact_summary } = comparison;

  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-card/40 p-5 backdrop-blur shadow-[0_0_48px_-20px_var(--primary)]">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <GitCompare className="h-4 w-4 text-primary" />
            <h3 className="text-base font-semibold text-foreground">Before vs After</h3>
          </div>
          <p className="text-xs text-muted-foreground">
            Compare the original recommendation with the adjusted analysis.
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-white/10 bg-background/40 px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
          {added_factor ? "New factor added" : "Assumptions adjusted"}
        </span>
      </div>

      {/* Two cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ComparisonCard label="original" summary={baseline} />
        <ComparisonCard label="adjusted" summary={adjusted} baseline={baseline} />
      </div>

      {/* Context below cards */}
      <div className="space-y-3 border-t border-white/8 pt-4">
        {/* Changed assumptions (from what-if) */}
        {changed_assumptions && changed_assumptions.length > 0 && (
          <ChangedAssumptionsList changes={changed_assumptions} />
        )}

        {/* Added factor (from add-factor) */}
        {added_factor && (
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
              Added market factor
            </p>
            <div className="rounded-lg border border-white/5 bg-background/30 p-3 space-y-2">
              <p className="text-sm text-foreground/90">{added_factor.description}</p>
              {added_factor.keywords.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {added_factor.keywords.map((kw) => (
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
            </div>
          </div>
        )}

        {/* Impact summary */}
        {impact_summary && (
          <div className="rounded-lg border border-white/5 bg-background/20 px-3.5 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Impact summary
            </p>
            <p className="text-sm leading-relaxed text-foreground/85">{impact_summary}</p>
          </div>
        )}
      </div>
    </div>
  );
}
