import { Button } from "@/components/ui/button";
import { ArrowRight, BarChart3 } from "lucide-react";
import { HeroRevenueCard } from "./HeroRevenueCard";

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
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[520px] opacity-70 blur-3xl"
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

      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
        <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-[1fr_400px] xl:grid-cols-[1fr_440px] xl:gap-16">

          {/* ── Left: hero text ───────────────────────────────────────────── */}
          <div className="text-center lg:text-left">

            {/* Brand mark */}
            <div className="mb-8 flex justify-center lg:justify-start">
              <div className="relative flex h-28 w-28 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/50 to-accent/35 shadow-[0_0_80px_-8px_var(--primary)] ring-1 ring-primary/30">
                {/* outer glow ring */}
                <div className="absolute inset-0 rounded-3xl opacity-40 blur-md bg-gradient-to-br from-primary/60 to-accent/40" />
                <img
                  src="/brand/logo.png"
                  alt="MarketPilot logo"
                  className="relative h-36 w-36 object-contain brightness-[2.2] drop-shadow-[0_0_10px_rgba(255,255,255,0.7)]"
                />
              </div>
            </div>

            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground shadow-[0_0_30px_-12px_var(--primary)] backdrop-blur">
              <BarChart3 className="h-3.5 w-3.5 text-primary" />
              {slogan}
            </span>

            <h1 className="mt-6 text-balance bg-gradient-to-b from-foreground via-foreground/90 to-primary/70 bg-clip-text text-5xl font-bold tracking-tight text-transparent sm:text-6xl">
              {headline}
            </h1>

            <p className="mx-auto mt-7 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground lg:mx-0 sm:text-lg">
              {subheadline}
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row lg:justify-start">
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

            <ul className="mt-10 flex flex-wrap items-center justify-center gap-x-3 gap-y-2.5 lg:justify-start">
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

          {/* ── Right: revenue preview card ───────────────────────────────── */}
          <HeroRevenueCard />

        </div>
      </div>
    </section>
  );
}
