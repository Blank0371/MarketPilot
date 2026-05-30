import { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import { BASELINE } from "@/lib/mockData";
import type { WhatIfOverrides } from "@/lib/types";

interface WhatIfControlProps {
  onChange: (overrides: WhatIfOverrides) => void;
}

interface SliderDef {
  key: keyof WhatIfOverrides;
  label: string;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
}

const SLIDERS: SliderDef[] = [
  {
    key: "monthly_rent",
    label: "Monthly rent",
    min: 1500,
    max: 14000,
    step: 100,
    format: (v) => `€${v.toLocaleString("en-US")}`,
  },
  {
    key: "average_basket_price",
    label: "Avg. basket price",
    min: 3,
    max: 20,
    step: 0.5,
    format: (v) => `€${v.toFixed(2)}`,
  },
  {
    key: "gross_margin_pct",
    label: "Gross margin",
    min: 30,
    max: 85,
    step: 1,
    format: (v) => `${v}%`,
  },
];

const DEFAULTS: Required<WhatIfOverrides> = {
  monthly_rent: BASELINE.monthly_rent,
  average_basket_price: BASELINE.average_basket_price,
  gross_margin_pct: BASELINE.gross_margin_pct,
};

export function WhatIfControl({ onChange }: WhatIfControlProps) {
  const [values, setValues] = useState<Required<WhatIfOverrides>>(DEFAULTS);

  const handleChange = useCallback(
    (key: keyof WhatIfOverrides, raw: string) => {
      const num = parseFloat(raw);
      if (isNaN(num)) return;
      const next = { ...values, [key]: num };
      setValues(next);
      onChange(next);
    },
    [values, onChange],
  );

  const reset = useCallback(() => {
    setValues(DEFAULTS);
    onChange(DEFAULTS);
  }, [onChange]);

  const isModified = SLIDERS.some(
    (s) => Math.abs(values[s.key] - DEFAULTS[s.key]) > 0.001,
  );

  return (
    <Card className="border-white/10 bg-card/60 backdrop-blur">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">What-if sensitivity</CardTitle>
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
        <CardDescription className="text-xs">
          Adjust assumptions to see how they shift the verdict in real time. No new
          forecast needed.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
          {SLIDERS.map((s) => (
            <SliderRow
              key={s.key}
              def={s}
              value={values[s.key]}
              defaultValue={DEFAULTS[s.key]}
              onChange={(v) => handleChange(s.key, String(v))}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SliderRow({
  def,
  value,
  defaultValue,
  onChange,
}: {
  def: SliderDef;
  value: number;
  defaultValue: number;
  onChange: (v: number) => void;
}) {
  const pct = ((value - def.min) / (def.max - def.min)) * 100;
  const isModified = Math.abs(value - defaultValue) > 0.001;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{def.label}</span>
        <span
          className="text-sm font-semibold tabular-nums transition-colors"
          style={{ color: isModified ? "var(--primary)" : "var(--foreground)" }}
        >
          {def.format(value)}
        </span>
      </div>
      <div className="relative flex items-center">
        <input
          type="range"
          min={def.min}
          max={def.max}
          step={def.step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="slider-thumb w-full cursor-pointer appearance-none rounded-full bg-secondary/60 h-1.5 outline-none"
          style={{
            backgroundImage: `linear-gradient(to right, var(--primary) ${pct}%, transparent ${pct}%)`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground/50">
        <span>{def.format(def.min)}</span>
        <span>{def.format(def.max)}</span>
      </div>
    </div>
  );
}
