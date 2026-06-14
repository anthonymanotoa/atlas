import type * as React from "react";
import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-16 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-[var(--shadow-xs)] outline-none transition-[color,box-shadow,border-color] field-sizing-content",
        "placeholder:text-muted-foreground/70",
        "focus-visible:border-[color-mix(in_oklch,var(--primary)_55%,var(--input))] focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
