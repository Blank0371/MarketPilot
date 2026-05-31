import { Button } from "@/components/ui/button";
import type { NavLink } from "@/lib/types";

interface HeaderProps {
  productName: string;
  navLinks: NavLink[];
  ctaLabel: string;
  onCta: () => void;
}

export function Header({ productName, navLinks, ctaLabel, onCta }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <a href="#top" className="flex items-center gap-2">
          <img
            src="/brand/logo.png"
            alt={`${productName} logo`}
            className="h-8 w-8 rounded-lg object-contain shadow-[0_0_24px_-6px_var(--primary)]"
          />
          <span className="text-base font-semibold tracking-tight text-foreground">
            {productName}
          </span>
        </a>
        <nav className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="relative text-sm font-medium text-muted-foreground transition-colors hover:text-foreground after:absolute after:-bottom-0.5 after:left-0 after:h-px after:w-0 after:bg-primary/60 after:transition-all after:duration-200 hover:after:w-full"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <Button
          size="sm"
          onClick={onCta}
          className="bg-gradient-to-r from-primary to-accent font-medium text-primary-foreground shadow-[0_0_20px_-6px_var(--primary)] hover:opacity-95"
        >
          {ctaLabel}
        </Button>
      </div>
    </header>
  );
}
