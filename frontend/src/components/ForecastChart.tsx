import {
  ComposedChart,
  Area,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { HistoricalPoint, ForecastBandPoint } from "@/lib/types";

interface ForecastChartProps {
  historical: HistoricalPoint[];
  forecast: ForecastBandPoint[];
}

interface MergedPoint {
  month: string;
  historical?: number;
  forecast_mid?: number;
  band_low?: number;
  /** high - low; stacked on top of band_low to paint the confidence region */
  band_range?: number;
}

function mergeData(historical: HistoricalPoint[], forecast: ForecastBandPoint[]): MergedPoint[] {
  const hist: MergedPoint[] = historical.map((p) => ({ month: p.month, historical: p.value }));

  // Connect last historical point into forecast so lines join seamlessly.
  const lastHist = historical[historical.length - 1];
  const forecastPoints: MergedPoint[] = forecast.map((p, i) => ({
    month: p.month,
    forecast_mid: p.mid,
    band_low: p.low,
    band_range: p.high - p.low,
    ...(i === 0 && lastHist ? { historical: lastHist.value } : {}),
  }));

  return [...hist, ...forecastPoints];
}

function fmtEUR(v: number) {
  return `€${v.toLocaleString("en-US")}`;
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const entries = payload.filter(
    (p) => p.value != null && p.name !== "band_low" && p.name !== "band_range",
  );
  return (
    <div className="rounded-xl border border-white/10 bg-card/95 px-3.5 py-3 text-xs shadow-xl backdrop-blur">
      <p className="mb-2 font-semibold text-foreground/70">{label}</p>
      {entries.map((e) => (
        <div key={e.name} className="flex items-center gap-2.5">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: e.color }} />
          <span className="text-muted-foreground capitalize">
            {e.name.replace("_", " ")}
          </span>
          <span className="ml-auto font-semibold text-foreground">{fmtEUR(e.value)}</span>
        </div>
      ))}
    </div>
  );
};

export function ForecastChart({ historical, forecast }: ForecastChartProps) {
  const data = mergeData(historical, forecast);

  // Mark where history ends and forecast begins.
  const splitMonth = forecast[0]?.month;

  // Show every 4th tick to avoid crowding.
  const ticks = data
    .map((d, i) => ({ month: d.month, i }))
    .filter(({ i }) => i % 4 === 0)
    .map(({ month }) => month);

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.04} />
            </linearGradient>
          </defs>

          <CartesianGrid
            stroke="var(--border)"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="month"
            ticks={ticks}
            stroke="var(--muted-foreground)"
            fontSize={10}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            stroke="var(--muted-foreground)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `€${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Forecast start marker */}
          {splitMonth && (
            <ReferenceLine
              x={splitMonth}
              stroke="var(--primary)"
              strokeOpacity={0.3}
              strokeDasharray="4 4"
              label={{
                value: "Forecast →",
                position: "insideTopLeft",
                fontSize: 9,
                fill: "var(--muted-foreground)",
                dy: -4,
              }}
            />
          )}

          {/* Confidence band: stacked area trick — band_low fills transparent, band_range fills colored */}
          <Area
            type="monotone"
            dataKey="band_low"
            stackId="band"
            stroke="none"
            fill="none"
            dot={false}
            activeDot={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="band_range"
            stackId="band"
            stroke="none"
            fill="url(#bandFill)"
            dot={false}
            activeDot={false}
            connectNulls
          />

          {/* Historical line */}
          <Line
            type="monotone"
            dataKey="historical"
            name="Historical"
            stroke="var(--primary)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "var(--primary)", stroke: "var(--background)", strokeWidth: 2 }}
            connectNulls={false}
          />

          {/* Forecast mid line (dashed continuation) */}
          <Line
            type="monotone"
            dataKey="forecast_mid"
            name="Forecast (mid)"
            stroke="var(--primary)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            activeDot={{ r: 4, fill: "var(--primary)", stroke: "var(--background)", strokeWidth: 2 }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
