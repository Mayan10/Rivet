import { cn } from "@/lib/utils";

/**
 * Hand-built architectural floor plan used as the hero visual — walls,
 * partitions, dimension lines, a door swing, room labels. Pure SVG, theme
 * aware via currentColor-mapped utility classes.
 */
export function FloorPlan({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 600 480"
      fill="none"
      className={cn("h-auto w-full", className)}
      role="img"
      aria-label="A generated residential floor plan with living, kitchen, bedroom, and bath."
    >
      {/* accent fill: the living room */}
      <rect x="40" y="60" width="300" height="230" className="fill-clay/10" />

      {/* outer walls (double line) */}
      <rect x="40" y="60" width="520" height="380" className="stroke-foreground" strokeWidth="3" />
      <rect x="48" y="68" width="504" height="364" className="stroke-foreground/30" strokeWidth="1" />

      {/* interior partitions */}
      <g className="stroke-foreground" strokeWidth="2">
        <line x1="340" y1="60" x2="340" y2="440" />
        <line x1="40" y1="290" x2="340" y2="290" />
        <line x1="340" y1="250" x2="560" y2="250" />
        <line x1="450" y1="250" x2="450" y2="440" />
      </g>

      {/* door openings (gaps drawn as paper-coloured overstrike) */}
      <g className="stroke-background" strokeWidth="4">
        <line x1="340" y1="150" x2="340" y2="200" />
        <line x1="150" y1="290" x2="200" y2="290" />
        <line x1="450" y1="330" x2="450" y2="370" />
      </g>

      {/* entry door + swing arc */}
      <g className="stroke-clay" strokeWidth="1.5">
        <path d="M40 380 A40 40 0 0 0 80 340" />
        <line x1="40" y1="380" x2="40" y2="340" />
      </g>

      {/* dimension line, top */}
      <g className="stroke-muted-foreground" strokeWidth="1">
        <line x1="40" y1="34" x2="560" y2="34" />
        <line x1="40" y1="28" x2="40" y2="40" />
        <line x1="340" y1="28" x2="340" y2="40" />
        <line x1="560" y1="28" x2="560" y2="40" />
      </g>

      {/* labels */}
      <g className="fill-muted-foreground font-mono" style={{ fontSize: 13 }}>
        <text x="300" y="22" textAnchor="middle" className="fill-muted-foreground">
          12.40 m
        </text>
        <text x="190" y="330" textAnchor="middle">KITCHEN</text>
        <text x="190" y="348" textAnchor="middle" className="fill-muted-foreground/70" style={{ fontSize: 11 }}>
          14.8 m²
        </text>
        <text x="450" y="150" textAnchor="middle">BEDROOM</text>
        <text x="450" y="168" textAnchor="middle" className="fill-muted-foreground/70" style={{ fontSize: 11 }}>
          16.2 m²
        </text>
        <text x="395" y="350" textAnchor="middle">BATH</text>
        <text x="505" y="350" textAnchor="middle">HALL</text>
      </g>

      {/* accent label for the living room */}
      <g className="font-mono" style={{ fontSize: 14 }}>
        <text x="190" y="170" textAnchor="middle" className="fill-clay font-semibold">
          LIVING
        </text>
        <text x="190" y="190" textAnchor="middle" className="fill-clay/70" style={{ fontSize: 11 }}>
          29.4 m²
        </text>
      </g>
    </svg>
  );
}
