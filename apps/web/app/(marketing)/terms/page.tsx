import type { Metadata } from "next";
import { Container } from "@/components/site/container";
import { Prose } from "@/components/site/prose";

// Placeholder terms — replace with counsel-reviewed copy before launch.
export const metadata: Metadata = {
  title: "Terms of Service",
  robots: { index: false },
};

export default function TermsPage() {
  return (
    <Container className="max-w-3xl py-20 sm:py-24">
      <p className="eyebrow">Legal</p>
      <h1 className="mt-4 font-display text-4xl font-semibold tracking-tight">
        Terms of Service
      </h1>
      <p className="mt-2 font-mono text-xs text-muted-foreground">
        Last updated: {new Date().getFullYear()}
      </p>

      <Prose className="mt-10">
        <h2>Acceptance</h2>
        <p>
          By creating an account or using Rivet, you agree to these terms. If
          you do not agree, do not use the service.
        </p>
        <h2>The service</h2>
        <p>
          Rivet generates residential floor plans from a room program. Plans are
          produced by an automated engine and are provided for design assistance
          only. They are not a substitute for review by a licensed architect or
          engineer, and you are responsible for verifying any output against the
          applicable local building code before use in construction.
        </p>
        <h2>Accounts and billing</h2>
        <p>
          Paid plans are billed in advance through Stripe. Usage limits apply per
          plan and reset each calendar month. You may cancel at any time; access
          continues until the end of the current billing period.
        </p>
        <h2>Acceptable use</h2>
        <p>
          Do not abuse, reverse-engineer, or attempt to disrupt the service, and
          do not use it to violate any law or third-party right.
        </p>
        <h2>Contact</h2>
        <p>
          Questions about these terms can be raised via the project&apos;s
          repository.
        </p>
      </Prose>
    </Container>
  );
}
