import { cn } from "@/lib/utils";

/** Typographic wrapper for long-form content (legal, docs, blog). */
export function Prose({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "text-sm leading-relaxed text-muted-foreground",
        "[&>p]:mt-4 [&>ul]:mt-4 [&>ul]:list-disc [&>ul]:space-y-2 [&>ul]:pl-5",
        "[&>h2]:mt-10 [&>h2]:font-display [&>h2]:text-xl [&>h2]:font-semibold [&>h2]:text-foreground",
        "[&_a]:text-clay [&_a]:underline [&_a]:underline-offset-4",
        className,
      )}
      {...props}
    />
  );
}
