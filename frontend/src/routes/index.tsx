import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { Stepper } from "@/components/Stepper";
import { PitchStep } from "@/components/PitchStep";
import { ConfirmDescriptions } from "@/components/ConfirmDescriptions";
import { PollingLoader } from "@/components/PollingLoader";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import {
  exampleChips,
  heroCopy,
  navLinks,
  pitchPlaceholder,
  productName,
  stepDefinitions,
  trustFeatures,
} from "@/lib/mockData";
import { extract, confirm, getStatus, getResult } from "@/lib/mockApi";
import type { Report, PipelineStep } from "@/lib/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MarketPilot — Navigate uncertainty before you launch" },
      {
        name: "description",
        content:
          "Turn a raw business idea into probabilistic forecasts and a clear go/no-go decision.",
      },
      { property: "og:title", content: "MarketPilot — Forecast-driven launch decisions" },
      {
        property: "og:description",
        content: "An investor-grade decision cockpit for evaluating new business ideas.",
      },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

type Phase = "idea" | "confirm" | "polling" | "results";

function Index() {
  const [phase, setPhase] = useState<Phase>("idea");
  const [extracting, setExtracting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [descriptions, setDescriptions] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pipelineStep, setPipelineStep] = useState<PipelineStep>("extracting");
  const [report, setReport] = useState<Report | null>(null);

  const workflowRef = useRef<HTMLDivElement>(null);

  const scrollToWorkflow = useCallback(() => {
    workflowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // ─── Step 1: extract descriptions from pitch ─────────────────────────────
  const handleExtract = async (pitchText: string) => {
    setExtracting(true);
    scrollToWorkflow();
    try {
      const payload = await extract(pitchText);
      setDescriptions(payload.descriptions);
      setPhase("confirm");
    } finally {
      setExtracting(false);
    }
  };

  // ─── Step 2: confirm descriptions, kick off job ───────────────────────────
  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const res = await confirm(descriptions);
      setJobId(res.job_id);
      setPipelineStep("extracting");
      setPhase("polling");
    } finally {
      setConfirming(false);
    }
  };

  // ─── Polling loop ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== "polling" || !jobId) return;

    const interval = setInterval(async () => {
      try {
        const status = await getStatus(jobId);
        setPipelineStep(status.step);
        if (status.done) {
          clearInterval(interval);
          const result = await getResult(jobId);
          setReport(result);
          setPhase("results");
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [phase, jobId]);

  // Map phase → stepper step
  const stepperCurrent: 1 | 2 | 3 =
    phase === "idea" ? 1 : phase === "confirm" || phase === "polling" ? 2 : 3;
  const stepperMaxReached: 1 | 2 | 3 =
    phase === "results" ? 3 : phase === "confirm" || phase === "polling" ? 2 : 1;

  return (
    <div id="top" className="min-h-screen bg-background text-foreground">
      <Header
        productName={productName}
        navLinks={navLinks}
        ctaLabel={heroCopy.ctaLabel}
        onCta={scrollToWorkflow}
      />

      <main>
        <HeroSection
          headline={heroCopy.headline}
          slogan={heroCopy.slogan}
          subheadline={heroCopy.subheadline}
          features={trustFeatures}
          ctaLabel={heroCopy.ctaLabel}
          onStart={scrollToWorkflow}
        />

        <section
          id="how-it-works"
          ref={workflowRef}
          className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6 lg:px-8"
        >
          <div className="mb-8 max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
              Decision cockpit
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
              From idea to decision in minutes.
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Pitch the concept, confirm the extracted market drivers, then read the
              forecast-driven recommendation — with every assumption visible and
              adjustable.
            </p>
          </div>

          <div className="mb-8">
            <Stepper
              steps={stepDefinitions}
              current={stepperCurrent}
              maxReached={stepperMaxReached}
              onStepClick={(id) => {
                if (id === 1 && phase !== "polling") setPhase("idea");
                if (id === 2 && (phase === "results")) setPhase("confirm");
                if (id === 3 && phase === "results") setPhase("results");
              }}
            />
          </div>

          <div id="demo" className="scroll-mt-20">
            {phase === "idea" && (
              <PitchStep
                placeholder={pitchPlaceholder}
                examples={exampleChips}
                loading={extracting}
                onSubmit={handleExtract}
              />
            )}

            {phase === "confirm" && (
              <ConfirmDescriptions
                descriptions={descriptions}
                loading={confirming}
                onChange={setDescriptions}
                onConfirm={handleConfirm}
              />
            )}

            {phase === "polling" && (
              <div className="rounded-2xl border border-white/10 bg-card/60 shadow-[0_0_60px_-30px_var(--primary)] backdrop-blur">
                <PollingLoader step={pipelineStep} />
              </div>
            )}

            {phase === "results" && report && (
              <ResultsDashboard report={report} />
            )}
          </div>
        </section>
      </main>

      <footer className="border-t border-white/5 bg-background/40">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} {productName}. Forecast-driven launch decisions.</p>
          <p>{heroCopy.slogan}</p>
        </div>
      </footer>
    </div>
  );
}
