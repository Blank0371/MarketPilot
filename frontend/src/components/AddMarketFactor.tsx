import { useState, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, FlaskConical, Info } from "lucide-react";
import { mockAddMarketFactor } from "@/lib/mockApi";
import type { AddedMarketFactor } from "@/lib/mockApi";
import type { ComparisonResult, Report } from "@/lib/types";
import { AddedFactorList } from "./AddedFactorList";

interface AddMarketFactorProps {
  baseReport: Report;
  onComparisonUpdate: (comparison: ComparisonResult) => void;
}

const EXAMPLE_FACTORS = [
  "Energy cost development for small retail stores in Vienna",
  "Online ice cream delivery demand in Austria",
  "Tourism spending by visitors in Vienna's 1st district",
  "Premium retail spending trend in Vienna",
  "Seasonality of frozen dessert purchases in Austria",
];

export function AddMarketFactor({ baseReport, onComparisonUpdate }: AddMarketFactorProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [addedFactors, setAddedFactors] = useState<AddedMarketFactor[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = async (description: string) => {
    const trimmed = description.trim();
    if (!trimmed || loading) return;

    // Optimistically add a "running" placeholder
    const placeholder: AddedMarketFactor = {
      description: trimmed,
      keywords: [],
      status: "running",
    };
    setAddedFactors((prev) => [placeholder, ...prev]);
    setInput("");
    setLoading(true);

    try {
      // TODO: Replace with real call to /api/add-factor (see mockApi.ts for full shape).
      // The real endpoint returns a job_id that should be polled for status,
      // not a direct result — update this component to handle async polling.
      const result = await mockAddMarketFactor(trimmed, baseReport);

      const added: AddedMarketFactor = {
        description: trimmed,
        keywords: result.factor.keywords,
        status: "added",
        reason_for_update: result.reason_for_update,
      };

      setAddedFactors((prev) => [added, ...prev.slice(1)]);
      onComparisonUpdate(result.comparison);
    } catch {
      setAddedFactors((prev) => [
        { ...prev[0], status: "failed" },
        ...prev.slice(1),
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (ex: string) => {
    setInput(ex);
    textareaRef.current?.focus();
  };

  return (
    <Card className="border-white/10 bg-card/60 backdrop-blur">
      <CardHeader className="pb-4">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-accent" />
          <CardTitle className="text-base">Add another market factor</CardTitle>
        </div>
        <CardDescription className="text-xs max-w-xl">
          Test an additional external signal by sending it through the forecasting
          pipeline.
        </CardDescription>

        {/* Distinction callout */}
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-primary/15 bg-primary/5 px-3 py-2.5">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/80" />
          <p className="text-[11px] leading-snug text-foreground/75">
            <span className="font-semibold text-foreground/90">Different from What-if Sensitivity.</span>
            {" "}Adding a factor runs a new Sybilion forecast for that signal and incorporates
            its prediction into the analysis. What-if only adjusts economics — no new forecast.
          </p>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Input */}
        <div className="space-y-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Example: Energy cost development for small retail stores in Vienna"
            rows={2}
            disabled={loading}
            className="w-full resize-none rounded-xl border border-white/10 bg-background/60 px-3.5 py-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground/50 outline-none transition-colors focus:border-accent/50 focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
          />

          {/* Example chips */}
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLE_FACTORS.map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={loading}
                onClick={() => handleExampleClick(ex)}
                className="rounded-full border border-white/10 bg-secondary/40 px-2.5 py-1 text-[11px] text-foreground/70 transition-all hover:border-accent/40 hover:bg-accent/10 hover:text-foreground disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            The factor will be matched to a time-series signal and forecasted by
            Sybilion.
          </p>
          <Button
            onClick={() => submit(input)}
            disabled={loading || !input.trim()}
            size="sm"
            className="shrink-0 bg-gradient-to-r from-accent to-primary font-medium text-primary-foreground shadow-[0_0_20px_-6px_var(--accent)] hover:opacity-95"
          >
            {loading ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                Fetching time series and running forecast…
              </>
            ) : (
              <>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Analyze factor
              </>
            )}
          </Button>
        </div>

        {/* Added factors list */}
        {addedFactors.length > 0 && (
          <div className="border-t border-white/8 pt-4 space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
              Added factors ({addedFactors.length})
            </p>
            <AddedFactorList factors={addedFactors} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
