import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StepDefinition } from "@/lib/types";

interface StepperProps {
  steps: StepDefinition[];
  current: 1 | 2 | 3;
  maxReached: 1 | 2 | 3;
  onStepClick: (id: 1 | 2 | 3) => void;
}

export function Stepper({ steps, current, maxReached, onStepClick }: StepperProps) {
  return (
    <ol className="flex w-full flex-col gap-3 md:flex-row md:items-center md:gap-0">
      {steps.map((step, idx) => {
        const isComplete = step.id < current;
        const isActive = step.id === current;
        const isClickable = step.id <= maxReached;
        return (
          <li key={step.id} className="flex flex-1 items-center gap-3 md:gap-4">
            <button
              type="button"
              disabled={!isClickable}
              onClick={() => isClickable && onStepClick(step.id)}
              className={cn(
                "group flex flex-1 items-center gap-3 rounded-xl border px-3.5 py-3 text-left backdrop-blur transition-all",
                isActive
                  ? "border-primary/40 bg-primary/10 shadow-[0_0_28px_-12px_var(--primary)]"
                  : isComplete
                  ? "border-white/10 bg-card/50 hover:border-primary/30"
                  : "border-dashed border-white/10 bg-transparent",
                isClickable ? "cursor-pointer" : "cursor-not-allowed opacity-60",
              )}
            >
              <span
                className={cn(
                  "grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold transition-colors",
                  isComplete
                    ? "bg-gradient-to-br from-primary to-accent text-primary-foreground"
                    : isActive
                    ? "bg-gradient-to-br from-primary to-accent text-primary-foreground ring-4 ring-primary/20"
                    : "bg-secondary/60 text-muted-foreground",
                )}
              >
                {isComplete ? <Check className="h-4 w-4" /> : step.id}
              </span>
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-sm font-semibold leading-tight",
                    isActive ? "text-foreground" : "text-foreground/85",
                  )}
                >
                  {step.label}
                </p>
                <p className="truncate text-xs text-muted-foreground">{step.description}</p>
              </div>
            </button>
            {idx < steps.length - 1 && (
              <span className="hidden h-px flex-1 bg-gradient-to-r from-white/10 to-transparent md:block" aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}
