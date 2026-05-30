import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";

interface HeroSectionProps {
  headline: string;
  slogan: string;
  subheadline: string;
  features: string[];
  ctaLabel: string;
  onStart: () => void;
}

export function HeroSection({
  headline,
  slogan,
  subheadline,
  features,
  ctaLabel,
  onStart,
}: HeroSectionProps) {
  return (
    <section id="product" className="relative overflow-hidden border-b border-white/5">
      {/* Soft halo backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[480px] opacity-70 blur-3xl"
        style={{
          background:
            "radial-gradient(60% 60% at 50% 0%, color-mix(in oklab, var(--primary) 35%, transparent), transparent 70%)",
        }}
      />
      <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
        <div className="mx-auto max-w-4xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground shadow-[0_0_30px_-12px_var(--primary)] backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            {slogan}
          </span>
          <h1 className="mt-6 text-balance bg-gradient-to-b from-foreground to-foreground/70 bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-5xl lg:text-6xl">
            {headline}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            {subheadline}
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              onClick={onStart}
              className="bg-gradient-to-r from-primary to-accent font-medium text-primary-foreground shadow-[0_0_36px_-8px_var(--primary)] hover:opacity-95"
            >
              {ctaLabel}
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
            <a
              href="#how-it-works"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              See the flow
            </a>
          </div>
          <ul className="mt-10 flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
            {features.map((feature) => (
              <li
                key={feature}
                className="rounded-full border border-white/10 bg-card/60 px-3.5 py-1.5 text-xs font-medium text-foreground/85 shadow-sm backdrop-blur"
              >
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
