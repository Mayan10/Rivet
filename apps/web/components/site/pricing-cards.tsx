import Link from "next/link";
import { Check } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PLANS } from "@/lib/plans";

export function PricingCards() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {PLANS.map((plan) => (
        <div
          key={plan.code}
          className={cn(
            "relative flex flex-col rounded-lg border bg-card p-7",
            plan.featured
              ? "ticked border-clay/40 shadow-sm ring-1 ring-clay/20"
              : "border-border",
          )}
        >
          {plan.featured && (
            <span className="absolute -top-3 left-7 rounded-full bg-clay px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-clay-foreground">
              Most popular
            </span>
          )}

          <h3 className="font-display text-xl font-semibold">{plan.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{plan.tagline}</p>

          <div className="mt-6 flex items-baseline gap-1">
            <span className="font-display text-4xl font-semibold tracking-tight">
              ${plan.priceMonthly}
            </span>
            <span className="text-sm text-muted-foreground">/ month</span>
          </div>

          <ul className="mt-6 space-y-3 text-sm">
            {plan.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2.5">
                <Check className="mt-0.5 size-4 shrink-0 text-clay" />
                <span className="text-foreground/85">{feature}</span>
              </li>
            ))}
          </ul>

          <Link
            href="/signup"
            className={cn(
              buttonVariants({ variant: plan.featured ? "default" : "outline" }),
              "mt-8",
              plan.featured && "bg-clay text-clay-foreground hover:bg-clay/90",
            )}
          >
            {plan.cta}
          </Link>
        </div>
      ))}
    </div>
  );
}
