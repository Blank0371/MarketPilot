import { cn } from "@/lib/utils";
import type { PipelineStep } from "@/lib/types";
import { Search, Database, TrendingUp, FileText, CheckCircle2 } from "lucide-react";

interface PollingLoaderProps {
  step: PipelineStep;
}

const STEPS: Array<{
  id: PipelineStep;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  copy: string;
}> = [
  {
    id: "extracting",
    icon: Search,
    label: "Analyzing signals",
    copy: "Mapping your market factors to forecast-ready data descriptors.",
  },
  {
    id: "fetching",
    icon: Database,
    label: "Pulling time-series",
    copy: "Retrieving 60 months of historical data for each driver signal.",
  },
  {
    id: "forecasting",
    icon: TrendingUp,
    label: "Running probability engine",
    copy: "Sybilion is computing probabilistic forecast bands across all signals.",
  },
  {
    id: "reporting",
    icon: FileText,
    label: "Building your report",
    copy: "Synthesizing forecasts into revenue projections and a decision recommendation.",
  },
  {
    id: "done",
    icon: CheckCircle2,
    label: "Report ready",
    copy: "Your forecast-driven decision report is complete.",
  },
];

const STEP_ORDER: PipelineStep[] = ["extracting", "fetching", "forecasting", "reporting", "done"];

export function PollingLoader({ step }: PollingLoaderProps) {
  const currentIdx = STEP_ORDER.indexOf(step);
  const current = STEPS.find((s) => s.id === step) ?? STEPS[0];
  const Icon = current.icon;

  return (
    <div className="flex flex-col items-center gap-10 py-16 select-none">
      {/* Icon orb — single static glow, no ping rings */}
      <div className="relative flex items-center justify-center">
        {/* Soft ambient halo — CSS only, no animation */}
        <span
          className="absolute rounded-full opacity-20 blur-2xl"
          style={{
            width: 96,
            height: 96,
            background: "radial-gradient(circle, var(--primary), var(--accent))",
          }}
        />
        <span
          className="relative grid h-16 w-16 place-items-center rounded-full shadow-[0_0_48px_-8px_var(--primary)]"
          style={{
            background: "linear-gradient(135deg, var(--primary), var(--accent))",
          }}
        >
          <Icon className="h-7 w-7 text-white" />
        </span>
      </div>

      {/* Step label + copy */}
      <div className="text-center space-y-2 max-w-sm">
        <p className="text-lg font-semibold text-foreground">{current.label}</p>
        <p className="text-sm text-muted-foreground leading-relaxed">{current.copy}</p>
      </div>

      {/* Progress track — promoted as the primary progress indicator */}
      <ol className="flex items-center gap-0" aria-label="Pipeline progress">
        {STEPS.filter((s) => s.id !== "done").map((s, idx) => {
          const stepIdx = STEP_ORDER.indexOf(s.id);
          const done = stepIdx < currentIdx;
          const active = stepIdx === currentIdx;
          return (
            <li key={s.id} className="flex items-center">
              <div className="flex flex-col items-center gap-2">
                <div
                  className={cn(
                    "h-2.5 w-2.5 rounded-full transition-all duration-500",
                    done
                      ? "scale-100 bg-primary shadow-[0_0_8px_2px_var(--primary)]"
                      : active
                      ? "scale-125 bg-primary shadow-[0_0_12px_3px_var(--primary)] animate-pulse"
                      : "bg-secondary/60 scale-75",
                  )}
                />
                <span
                  className={cn(
                    "text-[10px] font-medium transition-colors hidden sm:block",
                    done
                      ? "text-primary/70"
                      : active
                      ? "text-foreground/90"
                      : "text-muted-foreground/40",
                  )}
                >
                  {s.label.split(" ")[0]}
                </span>
              </div>
              {idx < STEPS.length - 2 && (
                <div
                  className={cn(
                    "mx-3 h-px w-10 transition-all duration-700 sm:w-16",
                    done
                      ? "bg-gradient-to-r from-primary/40 to-primary/20"
                      : "bg-secondary/40",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
