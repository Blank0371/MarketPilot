import type { InvestmentItem } from "@/lib/types";

interface InvestmentBreakdownProps {
  items: InvestmentItem[];
}

const palette = [
  "var(--primary)",
  "var(--accent)",
  "var(--decision-launch)",
  "var(--decision-adapt)",
  "var(--decision-delay)",
  "var(--chart-3)",
];

function fmtEUR(n: number) {
  return `€${n.toLocaleString("en-US")}`;
}

export function InvestmentBreakdown({ items }: InvestmentBreakdownProps) {
  const total = items.reduce((acc, it) => acc + it.amount, 0);
  let cumulative = 0;
  const segments = items.map((it, i) => {
    const start = (cumulative / total) * 100;
    cumulative += it.amount;
    const end = (cumulative / total) * 100;
    return { ...it, start, end, color: palette[i % palette.length] };
  });

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Total estimated investment
        </p>
        <p className="text-2xl font-semibold tabular-nums text-foreground">
          {fmtEUR(total)}
        </p>
      </div>

      {/* stacked bar */}
      <div className="flex h-2.5 w-full overflow-hidden rounded-full border border-white/10 bg-background/40">
        {segments.map((s) => (
          <div
            key={s.category}
            title={`${s.category}: ${fmtEUR(s.amount)}`}
            style={{
              width: `${s.end - s.start}%`,
              background: s.color,
            }}
          />
        ))}
      </div>

      <ul className="space-y-2">
        {segments.map((s) => {
          const pct = Math.round((s.amount / total) * 100);
          return (
            <li
              key={s.category}
              className="flex items-center justify-between gap-3 rounded-lg border border-white/8 bg-background/40 px-3.5 py-3"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: s.color }}
                />
                <span className="truncate text-sm text-foreground/90">
                  {s.category}
                </span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="text-xs text-muted-foreground">{pct}%</span>
                <span className="text-sm font-medium text-foreground">
                  {fmtEUR(s.amount)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
