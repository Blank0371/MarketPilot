import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Wand2 } from "lucide-react";

interface PitchStepProps {
  placeholder: string;
  examples: string[];
  loading: boolean;
  onSubmit: (text: string) => void;
}

export function PitchStep({ placeholder, examples, loading, onSubmit }: PitchStepProps) {
  const [value, setValue] = useState("");

  return (
    <Card className="relative overflow-hidden border-white/10 bg-card/60 shadow-[0_0_60px_-30px_var(--primary)] backdrop-blur">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 right-0 h-64 w-64 rounded-full opacity-30 blur-3xl"
        style={{ background: "radial-gradient(circle, var(--primary), transparent 70%)" }}
      />
      <CardHeader className="space-y-1.5">
        <CardTitle className="text-xl">Describe your business idea</CardTitle>
        <CardDescription className="text-muted-foreground">
          Be specific about location, concept, and target customer. The agent extracts
          the quantifiable market factors that drive forecast accuracy.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          className="min-h-[180px] resize-y border-white/10 bg-background/60 text-base leading-relaxed backdrop-blur focus-visible:border-primary/60 focus-visible:ring-primary/30"
          disabled={loading}
        />
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Try an example
          </p>
          <div className="flex flex-wrap gap-2">
            {examples.map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={loading}
                onClick={() => setValue(ex)}
                className="rounded-full border border-white/10 bg-secondary/50 px-3 py-1.5 text-xs font-medium text-foreground/80 transition-all hover:border-primary/50 hover:bg-primary/10 hover:text-foreground disabled:opacity-60"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 pt-2">
          <p className="text-xs text-muted-foreground">
            Your idea will be parsed into market signal descriptions you can review
            before the forecast runs.
          </p>
          <Button
            onClick={() => onSubmit(value.trim() || placeholder)}
            disabled={loading}
            size="lg"
            className="bg-gradient-to-r from-primary to-accent font-medium text-primary-foreground shadow-[0_0_28px_-8px_var(--primary)] hover:opacity-95"
          >
            {loading ? (
              <>
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                Reading your idea…
              </>
            ) : (
              <>
                <Wand2 className="mr-1 h-4 w-4" />
                Analyze idea
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
