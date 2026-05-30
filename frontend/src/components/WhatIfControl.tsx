import type { AllowedOverride, OverrideValue } from "@/lib/types";

interface WhatIfControlProps {
  override: AllowedOverride;
  value: OverrideValue;
  isModified: boolean;
  onChange: (id: string, value: OverrideValue) => void;
}

export function WhatIfControl({ override: o, value, isModified, onChange }: WhatIfControlProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{o.label}</span>
        <span
          className="text-sm font-semibold tabular-nums transition-colors"
          style={{ color: isModified ? "var(--primary)" : "var(--foreground)" }}
        >
          {formatValue(o, value)}
        </span>
      </div>
      {o.description && (
        <p className="text-[10px] text-muted-foreground/60 leading-snug">{o.description}</p>
      )}
      {o.type === "select" ? (
        <SegmentedControl
          options={o.options ?? []}
          value={value as string}
          onChange={(v) => onChange(o.id, v)}
        />
      ) : (
        <RangeSlider override={o} value={value as number} onChange={(v) => onChange(o.id, v)} />
      )}
    </div>
  );
}

// ─── Range slider ─────────────────────────────────────────────────────────────

function RangeSlider({
  override: o,
  value,
  onChange,
}: {
  override: AllowedOverride;
  value: number;
  onChange: (v: number) => void;
}) {
  const min = o.min ?? 0;
  const max = o.max ?? 100;
  const step = computeStep(o);
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <>
      <div className="relative flex items-center">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="slider-thumb w-full cursor-pointer appearance-none rounded-full bg-secondary/60 h-1.5 outline-none"
          style={{
            backgroundImage: `linear-gradient(to right, var(--primary) ${pct}%, transparent ${pct}%)`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground/50">
        <span>{formatValue(o, min)}</span>
        <span>{formatValue(o, max)}</span>
      </div>
    </>
  );
}

// ─── Segmented control (for select type) ─────────────────────────────────────

function SegmentedControl({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex rounded-lg border border-white/10 bg-background/40 p-0.5 gap-0.5">
      {options.map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={
              active
                ? "flex-1 rounded-md px-2 py-1.5 text-[10px] font-semibold capitalize transition-all bg-primary text-primary-foreground shadow-sm"
                : "flex-1 rounded-md px-2 py-1.5 text-[10px] capitalize text-muted-foreground transition-all hover:bg-white/5 hover:text-foreground"
            }
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatValue(o: AllowedOverride, v: OverrideValue): string {
  const n = v as number;
  switch (o.type) {
    case "currency":
      return `€${Math.round(n).toLocaleString("en-US")}`;
    case "percentage":
      return `${Math.round(n * 100)}%`;
    case "number":
      return o.unit ? `${n} ${o.unit}` : `${n}`;
    case "select":
      return v as string;
  }
}

function computeStep(o: AllowedOverride): number {
  if (o.type === "percentage") return 0.01;
  if (o.type === "number") return 1;
  const range = (o.max ?? 100) - (o.min ?? 0);
  if (range >= 100000) return 1000;
  if (range >= 10000) return 100;
  if (range >= 1000) return 10;
  return 1;
}
