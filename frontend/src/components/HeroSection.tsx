import { Button } from "@/components/ui/button";
import { ArrowRight, BarChart3 } from "lucide-react";

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
      {/* Halo backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[520px] opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(70% 60% at 50% 0%, color-mix(in oklab, var(--primary) 38%, transparent), transparent 70%)",
        }}
      />
      {/* Grain overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0 opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8 lg:py-32">
        <div className="mx-auto max-w-4xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground shadow-[0_0_30px_-12px_var(--primary)] backdrop-blur">
            <BarChart3 className="h-3.5 w-3.5 text-primary" />
            {slogan}
          </span>

          <h1 className="mt-6 text-balance bg-gradient-to-b from-foreground via-foreground/90 to-primary/70 bg-clip-text text-5xl font-bold tracking-tight text-transparent sm:text-6xl lg:text-7xl">
            {headline}
          </h1>

          <p className="mx-auto mt-7 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            {subheadline}
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              onClick={onStart}
              className="bg-gradient-to-r from-primary to-accent px-6 font-semibold text-primary-foreground shadow-[0_0_48px_-8px_var(--primary)] hover:opacity-95"
            >
              {ctaLabel}
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
            <a
              href="#how-it-works"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              See how it works
            </a>
          </div>

          <ul className="mt-12 flex flex-wrap items-center justify-center gap-x-2 gap-y-2">
            {features.map((feature) => (
              <li
                key={feature}
                className="rounded-full border border-white/10 bg-card/60 px-3.5 py-1.5 text-xs font-medium text-foreground/80 shadow-sm backdrop-blur transition-colors hover:border-primary/30 hover:text-foreground"
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
