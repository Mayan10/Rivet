import type { Metadata } from "next";
import { Container } from "@/components/site/container";
import { Prose } from "@/components/site/prose";

// Placeholder privacy policy — replace with counsel-reviewed copy before launch.
export const metadata: Metadata = {
  title: "Privacy Policy",
  robots: { index: false },
};

export default function PrivacyPage() {
  return (
    <Container className="max-w-3xl py-20 sm:py-24">
      <p className="eyebrow">Legal</p>
      <h1 className="mt-4 font-display text-4xl font-semibold tracking-tight">
        Privacy Policy
      </h1>
      <p className="mt-2 font-mono text-xs text-muted-foreground">
        Last updated: {new Date().getFullYear()}
      </p>

      <Prose className="mt-10">
        <h2>What we collect</h2>
        <p>
          We collect the account details you provide (such as your email), the
          room programs and generations you create, and basic usage and billing
          records needed to operate the service.
        </p>
        <h2>How we use it</h2>
        <p>
          Your data is used to run the engine, store your projects and history,
          enforce plan limits, and process payments. We do not sell your data.
        </p>
        <h2>Processors</h2>
        <p>
          Payments are handled by Stripe. Infrastructure and storage are hosted
          with our cloud provider. These processors handle data only to provide
          their service to us.
        </p>
        <h2>Retention and deletion</h2>
        <p>
          Generation history is retained per your plan. You can delete your
          account at any time, which removes your projects and associated data.
        </p>
        <h2>Contact</h2>
        <p>
          Questions about privacy can be raised via the project&apos;s
          repository.
        </p>
      </Prose>
    </Container>
  );
}
