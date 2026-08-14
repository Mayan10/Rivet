// Plan tiers for the marketing site. Mirrors apps/api/rivet_service/billing/plans.py
// (the backend is the source of truth for enforcement); keep the two in sync
// when tiers change. Prices are the plan definitions, billed via Stripe.

export type Plan = {
  code: "free" | "pro" | "studio";
  name: string;
  priceMonthly: number;
  tagline: string;
  features: string[];
  cta: string;
  featured?: boolean;
};

export const PLANS: Plan[] = [
  {
    code: "free",
    name: "Free",
    priceMonthly: 0,
    tagline: "Try the engine on real plots.",
    features: [
      "5 generations / month",
      "1 candidate per run",
      "PNG & SVG export (watermarked)",
      "7-day history",
    ],
    cta: "Start free",
  },
  {
    code: "pro",
    name: "Pro",
    priceMonthly: 29,
    tagline: "For practising designers and builders.",
    features: [
      "200 generations / month",
      "3 candidates per run",
      "DXF export for CAD",
      "No watermark",
      "Unlimited history",
    ],
    cta: "Go Pro",
    featured: true,
  },
  {
    code: "studio",
    name: "Studio",
    priceMonthly: 99,
    tagline: "For studios shipping plans at volume.",
    features: [
      "1,000 generations / month",
      "5 candidates per run",
      "API access",
      "Priority queue",
      "Everything in Pro",
    ],
    cta: "Choose Studio",
  },
];
