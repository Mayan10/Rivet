import Link from "next/link";
import { cn } from "@/lib/utils";

/** Wordmark with a small floor-plan mark: a plot divided by a guillotine cut. */
export function Logo({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={cn(
        "group inline-flex items-center gap-2.5 font-display text-lg font-semibold tracking-tight",
        className,
      )}
      aria-label="Rivet home"
    >
      <svg
        width="26"
        height="26"
        viewBox="0 0 26 26"
        fill="none"
        aria-hidden
        className="shrink-0"
      >
        <rect
          x="1.5"
          y="1.5"
          width="23"
          height="23"
          rx="2"
          className="stroke-foreground"
          strokeWidth="1.5"
        />
        {/* one horizontal + one vertical cut = a slicing-tree partition */}
        <line x1="10" y1="1.5" x2="10" y2="24.5" className="stroke-foreground" strokeWidth="1.25" />
        <line x1="10" y1="14" x2="24.5" y2="14" className="stroke-foreground" strokeWidth="1.25" />
        <rect x="1.5" y="1.5" width="8.5" height="12.5" className="fill-clay/80" />
      </svg>
      <span>Rivet</span>
    </Link>
  );
}
