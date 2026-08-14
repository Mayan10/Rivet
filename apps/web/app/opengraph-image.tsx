import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Rivet — Generative Floor Plan Engine";

const PAPER = "#F3EFE6";
const INK = "#26231D";
const CLAY = "#BE5B2E";
const LINE = "#D8D0BF";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: PAPER,
          padding: "72px 80px",
          // faint blueprint grid
          backgroundImage: `linear-gradient(${LINE} 1px, transparent 1px), linear-gradient(90deg, ${LINE} 1px, transparent 1px)`,
          backgroundSize: "48px 48px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", width: 40, height: 40, border: `3px solid ${INK}` }}>
            <div style={{ width: 16, height: 40, background: CLAY }} />
          </div>
          <div style={{ fontSize: 30, fontWeight: 700, color: INK }}>Rivet</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              fontSize: 20,
              letterSpacing: 6,
              textTransform: "uppercase",
              color: CLAY,
            }}
          >
            Generative Floor Plan Engine
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 72,
              fontWeight: 700,
              color: INK,
              lineHeight: 1.05,
              marginTop: 20,
              maxWidth: 900,
            }}
          >
            Floor plans that respect the building code.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ width: 64, height: 4, background: CLAY }} />
          <div style={{ fontSize: 24, color: "#6F675A" }}>
            Search · validate · render · export to DXF
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
