import type { Metadata } from "next";
import { Geist, Geist_Mono, Fraunces } from "next/font/google";
import { JsonLd } from "@/components/site/json-ld";
import { siteUrl } from "@/lib/site";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Rivet — Generative Floor Plan Engine",
    template: "%s · Rivet",
  },
  description:
    "Generate code-compliant residential floor plans from a room program, then render and export them to PNG, SVG, and DXF.",
  keywords: [
    "floor plan generator",
    "generative architecture",
    "residential floor plans",
    "DXF export",
    "building code compliant",
    "TNCDBR",
  ],
  openGraph: {
    type: "website",
    url: siteUrl,
    siteName: "Rivet",
    title: "Rivet — Generative Floor Plan Engine",
    description:
      "Code-compliant residential floor plans from a room program. Search, validate, render, and export to DXF.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Rivet — Generative Floor Plan Engine",
    description:
      "Code-compliant residential floor plans from a room program. Search, validate, render, and export to DXF.",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full`}
    >
      <body className="min-h-full">
        <JsonLd />
        {children}
      </body>
    </html>
  );
}
