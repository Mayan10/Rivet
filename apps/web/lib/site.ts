// Single source of truth for the site's public origin, consumed by canonical
// URLs, Open Graph, the sitemap, robots, and JSON-LD. Set NEXT_PUBLIC_SITE_URL
// on every non-local deployment. On Vercel, VERCEL_URL is picked up
// automatically. localhost is only ever used in local development.
function resolveSiteUrl(): string {
  if (process.env.NEXT_PUBLIC_SITE_URL) return process.env.NEXT_PUBLIC_SITE_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === "production") {
    // Never silently bake localhost into production SEO surfaces.
    console.warn(
      "[rivet] NEXT_PUBLIC_SITE_URL is not set for this production build; " +
        "SEO URLs (canonical, OG, sitemap, robots, JSON-LD) will fall back to " +
        "localhost. Set NEXT_PUBLIC_SITE_URL to the public origin before deploying.",
    );
  }
  return "http://localhost:3000";
}

export const siteUrl = resolveSiteUrl();
