import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useRef, useState } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { Stepper } from "@/components/Stepper";
import { PitchStep } from "@/components/PitchStep";
import { DynamicReviewStep } from "@/components/DynamicReviewStep";
import { ResultsDashboard } from "@/components/ResultsDashboard";
import {
  exampleChips,
  graphLabels,
  heroCopy,
  navLinks,
  pitchPlaceholder,
  productName,
  stepDefinitions,
  trustFeatures,
} from "@/lib/mockData";
import { calculateResult, extractFields } from "@/lib/mockApi";
import type { CalculationResult, EditableFieldGroup } from "@/lib/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MarketPilot — Navigate uncertainty before you launch" },
      {
        name: "description",
        content:
          "MarketPilot converts an unstructured business idea into editable assumptions, market signals, probabilistic forecasts, financial projections, and a clear go/no-go recommendation.",
      },
      { property: "og:title", content: "MarketPilot — Forecast-driven launch decisions" },
      {
        property: "og:description",
        content:
          "An investor-grade decision cockpit for evaluating new business ideas before you launch.",
      },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

function Index() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [maxReached, setMaxReached] = useState<1 | 2 | 3>(1);
  const [fieldGroups, setFieldGroups] = useState<EditableFieldGroup[] | null>(null);
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const workflowRef = useRef<HTMLDivElement>(null);

  const scrollToWorkflow = useCallback(() => {
    workflowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const handleExtract = async (pitchText: string) => {
    setExtracting(true);
    try {
      const groups = await extractFields(pitchText);
      setFieldGroups(groups);
      setStep(2);
      setMaxReached((m) => (m < 2 ? 2 : m));
    } finally {
      setExtracting(false);
    }
  };

  const handleCalculate = async () => {
    if (!fieldGroups) return;
    setCalculating(true);
    try {
      const res = await calculateResult(fieldGroups);
      setResult(res);
      setStep(3);
      setMaxReached(3);
    } finally {
      setCalculating(false);
    }
  };

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
              Pitch the concept, edit the structured assumptions, then read the forecast-driven recommendation.
            </p>
          </div>

          <div className="mb-8">
            <Stepper
              steps={stepDefinitions}
              current={step}
              maxReached={maxReached}
              onStepClick={(id) => setStep(id)}
            />
          </div>

          <div id="demo" className="scroll-mt-20">
            {step === 1 && (
              <PitchStep
                placeholder={pitchPlaceholder}
                examples={exampleChips}
                loading={extracting}
                onSubmit={handleExtract}
              />
            )}

            {step === 2 && fieldGroups && (
              <DynamicReviewStep
                groups={fieldGroups}
                loading={calculating}
                onChange={setFieldGroups}
                onCalculate={handleCalculate}
              />
            )}

            {step === 3 && result && (
              <ResultsDashboard result={result} graphLabels={graphLabels} />
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
