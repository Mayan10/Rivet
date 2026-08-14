import { Button } from "@/components/ui/button";

// Placeholder scaffold page. The real marketing landing arrives in Phase F2.
export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
      <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">
        Frontend scaffold · Phase F1
      </span>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Rivet</h1>
      <p className="max-w-md text-balance text-muted-foreground">
        Generative floor plans from a room program — code-compliant, rendered,
        and exported to DXF. Marketing site and app land in the next phases.
      </p>
      <Button>Get started</Button>
    </main>
  );
}
