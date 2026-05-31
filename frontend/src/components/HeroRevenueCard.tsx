import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp } from "lucide-react";

// ─── Static demo data — 12 monthly revenue points ────────────────────────────

const RAW = [18800, 20100, 21900, 24400, 27100, 29800, 32100, 33700, 35200, 38900, 41200, 42800];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const CHART_DATA = MONTHS.map((month, i) => ({
  month,
  revenue: RAW[i],
  // Confidence band: ±13% around the revenue line (stacked area technique)
  band_low: Math.round(RAW[i] * 0.87),
  band_range: Math.round(RAW[i] * 0.26), // high = revenue×1.13; range = high − low = revenue×0.26
}));

// ─── Custom tooltip ───────────────────────────────────────────────────────────

const HeroTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const entry = payload.find((p) => p.dataKey === "revenue");
  if (!entry) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-card/95 px-3 py-2.5 text-xs shadow-xl backdrop-blur">
      <p className="font-semibold text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-bold text-primary">
        €{entry.value.toLocaleString("en-US")}
      </p>
    </div>
  );
};

// ─── Component ────────────────────────────────────────────────────────────────

export function HeroRevenueCard() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-card/60 p-5 shadow-[0_0_60px_-20px_var(--primary)] backdrop-blur">
      {/* Ambient corner glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full opacity-[0.18] blur-3xl"
        style={{ background: "var(--primary)" }}
      />

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="relative">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Projected Monthly Revenue
        </p>

        <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-3xl font-bold tabular-nums tracking-tight text-foreground">
            €42,800
          </span>
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-decision-launch">
            <TrendingUp className="h-3.5 w-3.5" />
            +12.4% expected
          </span>
        </div>

        <p className="mt-1 text-xs text-muted-foreground">
          Expected baseline after launch
        </p>
      </div>

      {/* ── Chart ─────────────────────────────────────────────────────────── */}
      <div className="relative mt-4 h-[152px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={CHART_DATA}
            margin={{ top: 4, right: 2, left: -18, bottom: 0 }}
          >
            <defs>
              {/* Main revenue area fill */}
              <linearGradient id="heroRevenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.26} />
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.02} />
              </linearGradient>
              {/* Confidence band fill — paints only above the revenue line */}
              <linearGradient id="heroBandFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.11} />
                <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke="var(--border)"
              strokeDasharray="3 3"
              vertical={false}
            />

            <XAxis
              dataKey="month"
              ticks={["Jan", "Apr", "Jul", "Oct", "Dec"]}
              stroke="var(--muted-foreground)"
              fontSize={9}
              tickLine={false}
              axisLine={false}
            />

            <YAxis
              domain={[14000, 46000]}
              tickFormatter={(v: number) => `€${Math.round(v / 1000)}k`}
              stroke="var(--muted-foreground)"
              fontSize={9}
              tickLine={false}
              axisLine={false}
              width={36}
            />

            <Tooltip content={<HeroTooltip />} />

            {/* Confidence band (stacked area — paints above revenue line) */}
            <Area
              type="monotone"
              dataKey="band_low"
              stackId="heroBand"
              stroke="none"
              fill="none"
              dot={false}
              activeDot={false}
              legendType="none"
            />
            <Area
              type="monotone"
              dataKey="band_range"
              stackId="heroBand"
              stroke="none"
              fill="url(#heroBandFill)"
              dot={false}
              activeDot={false}
              legendType="none"
            />

            {/* Main revenue area */}
            <Area
              type="monotone"
              dataKey="revenue"
              stroke="var(--primary)"
              strokeWidth={2}
              fill="url(#heroRevenueFill)"
              dot={false}
              activeDot={{
                r: 4,
                fill: "var(--primary)",
                stroke: "var(--background)",
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* ── Mini stats ────────────────────────────────────────────────────── */}
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/8 pt-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Confidence
          </p>
          <p className="mt-1.5 text-xl font-semibold tabular-nums text-primary">
            90%
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Break-even
          </p>
          <p className="mt-1.5 text-xl font-semibold text-foreground">
            Month 7
          </p>
        </div>
      </div>
    </div>
  );
}
