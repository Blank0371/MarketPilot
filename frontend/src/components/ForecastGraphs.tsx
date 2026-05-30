import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ForecastChart } from "./ForecastChart";
import type { GraphsMap } from "@/lib/types";

interface ForecastGraphsProps {
  graphs: GraphsMap;
  labels?: Record<string, string>;
}

function prettify(key: string): string {
  return key
    .split("_")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}

export function ForecastGraphs({ graphs, labels = {} }: ForecastGraphsProps) {
  const entries = Object.entries(graphs);
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
      {entries.map(([key, series]) => (
        <Card
          key={key}
          className="border-white/10 bg-card/60 shadow-[0_0_40px_-24px_var(--primary)] backdrop-blur"
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-foreground/90">
              {labels[key] ?? prettify(key)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ForecastChart data={series} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
