import Link from "next/link";
import { Container } from "./container";
import { Logo } from "./logo";

const COLUMNS: { heading: string; links: { href: string; label: string }[] }[] =
  [
    {
      heading: "Product",
      links: [
        { href: "/#features", label: "Features" },
        { href: "/#process", label: "How it works" },
        { href: "/pricing", label: "Pricing" },
      ],
    },
    {
      heading: "Company",
      links: [
        { href: "/terms", label: "Terms" },
        { href: "/privacy", label: "Privacy" },
        {
          href: "https://github.com/Mayan10/Rivet",
          label: "GitHub",
        },
      ],
    },
  ];

export function SiteFooter() {
  return (
    <footer className="border-t border-border/70">
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <Logo />
          <p className="mt-4 max-w-xs text-sm text-muted-foreground">
            A generative floor plan engine. Search, validate, render, and
            export code-compliant residential layouts.
          </p>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.heading}>
            <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">
              {col.heading}
            </h3>
            <ul className="mt-4 space-y-3">
              {col.links.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-foreground/80 transition-colors hover:text-clay"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Container>

      <div className="border-t border-border/70">
        <Container className="flex flex-col items-start justify-between gap-2 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} Rivet. All rights reserved.</p>
          <p className="font-mono tracking-wide">
            TNCDBR 2019 · NBC 2016 rulesets
          </p>
        </Container>
      </div>
    </footer>
  );
}
