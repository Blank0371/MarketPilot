import { useState, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SlidersHorizontal, RotateCcw, Loader2 } from "lucide-react";
import { allowedOverrides } from "@/lib/mockData";
import { mockRecalculateWithOverrides } from "@/lib/mockApi";
import { WhatIfControl } from "./WhatIfControl";
import type { OverridesMap, OverrideValue, ComparisonResult, Report } from "@/lib/types";

interface WhatIfSensitivityProps {
  baseReport: Report;
  onComparisonUpdate: (comparison: ComparisonResult | null) => void;
}

function buildDefaults(): OverridesMap {
  return Object.fromEntries(
    allowedOverrides.map((o) => [o.id, o.base_value]),
  );
}

const DEFAULTS = buildDefaults();

export function WhatIfSensitivity({ baseReport, onComparisonUpdate }: WhatIfSensitivityProps) {
  const [values, setValues] = useState<OverridesMap>(DEFAULTS);
  const [calculating, setCalculating] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isModified = allowedOverrides.some((o) => {
    const cur = values[o.id];
    const base = o.base_value;
    if (typeof cur === "number" && typeof base === "number")
      return Math.abs(cur - base) > 0.001;
    return cur !== base;
  });

  const scheduleRecalculate = useCallback(
    (next: OverridesMap) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        setCalculating(true);
        try {
          const result = await mockRecalculateWithOverrides(baseReport, next);
          onComparisonUpdate(result);
        } finally {
          setCalculating(false);
        }
      }, 280); // TODO: increase debounce to ~500ms when wired to a real backend
    },
    [baseReport, onComparisonUpdate],
  );

  const handleChange = useCallback(
    (id: string, value: OverrideValue) => {
      const next = { ...values, [id]: value };
      setValues(next);
      scheduleRecalculate(next);
    },
    [values, scheduleRecalculate],
  );

  const reset = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setValues(DEFAULTS);
    onComparisonUpdate(null);
  }, [onComparisonUpdate]);

  return (
    <Card className="border-white/10 bg-card/60 backdrop-blur">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">What-if Sensitivity</CardTitle>
            {calculating && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary/70" />
            )}
          </div>
          {isModified && (
            <button
              type="button"
              onClick={reset}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
            >
              <RotateCcw className="h-3 w-3" />
              Reset
            </button>
          )}
        </div>
        <CardDescription className="text-xs max-w-xl">
          Adjust founder-controllable assumptions to see how they shift the verdict in real
          time. No new forecast needed — the Sybilion forecast stays fixed; only the
          economics recompute.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {allowedOverrides.map((o) => (
            <WhatIfControl
              key={o.id}
              override={o}
              value={values[o.id]}
              isModified={(() => {
                const cur = values[o.id];
                const base = o.base_value;
                if (typeof cur === "number" && typeof base === "number")
                  return Math.abs(cur - base) > 0.001;
                return cur !== base;
              })()}
              onChange={handleChange}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
