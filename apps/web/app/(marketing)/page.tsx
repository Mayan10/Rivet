import Link from "next/link";
import { ArrowRight, Ruler, ShieldCheck, FileDown, Compass } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Container } from "@/components/site/container";
import { FloorPlan } from "@/components/site/floor-plan";
import { PricingCards } from "@/components/site/pricing-cards";

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Code-compliant by construction",
    body: "Building-code minimums are hard constraints in a validator, not soft preferences. A layout that violates a setback or room minimum is never returned — you get an infeasibility result instead.",
  },
  {
    icon: Ruler,
    title: "A real search, not a template",
    body: "A guillotine slicing tree searched by simulated annealing explores thousands of partitions, scoring circulation, proportion, and adjacency to land on layouts that actually work.",
  },
  {
    icon: FileDown,
    title: "Deliverables, not screenshots",
    body: "Every plan renders to crisp PNG and SVG, and exports to DXF as a real CAD deliverable — dimensioned, layered, and ready to open in your drafting tool.",
  },
  {
    icon: Compass,
    title: "Vastu, optional and honest",
    body: "Directional Vastu-Shastra scoring is a soft preference you can switch on — it nudges the search without ever overriding a code minimum. Aesthetics and code stay separate.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Describe the program",
    body: "Give Rivet the plot dimensions and the rooms you need — areas, counts, a few adjacencies. No modelling, no drawing.",
  },
  {
    n: "02",
    title: "Search & validate",
    body: "The engine anneals through partitions, rejects anything that breaks code, and scores the survivors on circulation and proportion.",
  },
  {
    n: "03",
    title: "Render & export",
    body: "Pick from the ranked candidates and export to PNG, SVG, or a dimensioned DXF for your CAD workflow.",
  },
];

export default function LandingPage() {
  return (
    <>
      {/* ---- Hero ---------------------------------------------------------- */}
      <section className="relative overflow-hidden">
        <div className="blueprint-grid blueprint-grid-fade pointer-events-none absolute inset-0" />
        <Container className="relative grid gap-12 py-20 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:py-28">
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
            <p className="eyebrow">Generative floor plan engine</p>
            <h1 className="mt-5 text-balance font-display text-5xl font-semibold leading-[1.02] tracking-tight sm:text-6xl">
              Floor plans that respect the{" "}
              <span className="text-clay">building code</span>.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted-foreground">
              Rivet turns a room program into ranked, code-compliant
              residential layouts — searched, validated, rendered, and exported
              to DXF. From brief to buildable in seconds.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                href="/signup"
                className={cn(
                  buttonVariants({ size: "lg" }),
                  "bg-clay text-clay-foreground hover:bg-clay/90",
                )}
              >
                Start free <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/#process"
                className={buttonVariants({ size: "lg", variant: "outline" })}
              >
                See how it works
              </Link>
            </div>
            <p className="mt-6 font-mono text-xs text-muted-foreground">
              5 free generations / month · no card required
            </p>
          </div>

          <div className="ticked animate-in fade-in slide-in-from-bottom-6 rounded-lg border border-border bg-card/60 p-6 duration-1000 sm:p-8">
            <FloorPlan />
          </div>
        </Container>
      </section>

      {/* ---- Features ------------------------------------------------------ */}
      <section id="features" className="border-t border-border/70 py-20 sm:py-28">
        <Container>
          <div className="max-w-2xl">
            <p className="eyebrow">Why Rivet</p>
            <h2 className="mt-4 text-balance font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              An engine that knows the difference between a rule and a
              preference.
            </h2>
          </div>

          <div className="mt-14 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2">
            {FEATURES.map((feature) => (
              <div key={feature.title} className="bg-card p-8">
                <feature.icon className="size-6 text-clay" strokeWidth={1.5} />
                <h3 className="mt-5 font-display text-lg font-semibold">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {feature.body}
                </p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      {/* ---- Process ------------------------------------------------------- */}
      <section id="process" className="border-t border-border/70 py-20 sm:py-28">
        <Container>
          <div className="max-w-2xl">
            <p className="eyebrow">How it works</p>
            <h2 className="mt-4 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Three steps from program to plan.
            </h2>
          </div>

          <div className="mt-14 grid gap-8 md:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.n} className="relative">
                <span className="font-mono text-sm text-clay">{step.n}</span>
                <div className="mt-3 h-px w-full bg-border" />
                <h3 className="mt-5 font-display text-xl font-semibold">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      {/* ---- Pricing teaser ------------------------------------------------ */}
      <section className="border-t border-border/70 py-20 sm:py-28">
        <Container>
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
            <div className="max-w-2xl">
              <p className="eyebrow">Pricing</p>
              <h2 className="mt-4 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
                Start free. Scale when you ship.
              </h2>
            </div>
            <Link
              href="/pricing"
              className="group inline-flex items-center gap-1.5 text-sm font-medium text-clay"
            >
              Compare plans
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>

          <div className="mt-12">
            <PricingCards />
          </div>
        </Container>
      </section>

      {/* ---- CTA ----------------------------------------------------------- */}
      <section className="border-t border-border/70">
        <Container className="py-20 sm:py-24">
          <div className="ticked relative overflow-hidden rounded-lg border border-border bg-card px-8 py-14 text-center sm:px-16">
            <div className="blueprint-grid blueprint-grid-fade pointer-events-none absolute inset-0 opacity-60" />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-balance font-display text-3xl font-semibold tracking-tight sm:text-4xl">
                Put the engine to work on your next plot.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
                Generate your first compliant layout in under a minute.
              </p>
              <Link
                href="/signup"
                className={cn(
                  buttonVariants({ size: "lg" }),
                  "mt-8 bg-clay text-clay-foreground hover:bg-clay/90",
                )}
              >
                Start free <ArrowRight className="size-4" />
              </Link>
            </div>
          </div>
        </Container>
      </section>
    </>
  );
}
