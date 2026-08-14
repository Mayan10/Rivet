import { PLANS } from "@/lib/plans";
import { siteUrl } from "@/lib/site";

// Organization + WebSite + SoftwareApplication structured data for rich results.
const schema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteUrl}#organization`,
      name: "Rivet",
      url: siteUrl,
      description: "A generative floor plan engine.",
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl}#website`,
      url: siteUrl,
      name: "Rivet",
      publisher: { "@id": `${siteUrl}#organization` },
    },
    {
      "@type": "SoftwareApplication",
      name: "Rivet",
      applicationCategory: "DesignApplication",
      operatingSystem: "Web",
      description:
        "Generate code-compliant residential floor plans from a room program, then render and export to PNG, SVG, and DXF.",
      offers: PLANS.map((plan) => ({
        "@type": "Offer",
        name: plan.name,
        price: String(plan.priceMonthly),
        priceCurrency: "USD",
        url: `${siteUrl}/pricing`,
      })),
    },
  ],
};

export function JsonLd() {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
