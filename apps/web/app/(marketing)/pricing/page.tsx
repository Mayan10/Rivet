import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Container } from "@/components/site/container";
import { PricingCards } from "@/components/site/pricing-cards";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple plans for Rivet — start free, then upgrade for DXF export, more generations, and API access. Free, Pro ($29/mo), and Studio ($99/mo).",
  alternates: { canonical: "/pricing" },
};

const FAQS = [
  {
    q: "How is a generation counted?",
    a: "One generation is one run of the engine for a room program, returning your plan's ranked candidates. Your monthly allowance resets on the first of each calendar month.",
  },
  {
    q: "What does code-compliant actually mean?",
    a: "Building-code minimums — setbacks, room minimums — are hard constraints. Rivet ships swappable rulesets (TNCDBR 2019 primary, NBC 2016 fallback) and will return an infeasibility result rather than a layout that violates one.",
  },
  {
    q: "When do I get DXF export?",
    a: "DXF export is included on Pro and Studio. Free plans export watermarked PNG and SVG so you can evaluate the engine on real plots first.",
  },
  {
    q: "Can I change or cancel my plan?",
    a: "Yes. Billing is handled through Stripe's customer portal — upgrade, downgrade, or cancel anytime, and changes take effect from your next cycle.",
  },
];

export default function PricingPage() {
  return (
    <>
      <section className="relative overflow-hidden border-b border-border/70">
        <div className="blueprint-grid blueprint-grid-fade pointer-events-none absolute inset-0" />
        <Container className="relative py-20 text-center sm:py-24">
          <p className="eyebrow">Pricing</p>
          <h1 className="mx-auto mt-5 max-w-3xl text-balance font-display text-4xl font-semibold tracking-tight sm:text-5xl">
            Plans that scale with your practice.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            Start free on real plots. Upgrade when you need DXF, more runs, or
            API access. No card required to begin.
          </p>
        </Container>
      </section>

      <section className="py-16 sm:py-20">
        <Container>
          <PricingCards />
          <p className="mt-8 text-center font-mono text-xs text-muted-foreground">
            Prices in USD, billed monthly via Stripe · cancel anytime
          </p>
        </Container>
      </section>

      <section className="border-t border-border/70 py-20 sm:py-24">
        <Container className="max-w-3xl">
          <h2 className="font-display text-3xl font-semibold tracking-tight">
            Frequently asked
          </h2>
          <dl className="mt-10 divide-y divide-border">
            {FAQS.map((faq) => (
              <div key={faq.q} className="py-6">
                <dt className="font-display text-lg font-semibold">{faq.q}</dt>
                <dd className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {faq.a}
                </dd>
              </div>
            ))}
          </dl>

          <div className="mt-10">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-1.5 text-sm font-medium text-clay"
            >
              Still deciding? Start on the free plan
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </Container>
      </section>
    </>
  );
}
