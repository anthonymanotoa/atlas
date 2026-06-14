import type * as React from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-[var(--shadow-xs)] outline-none transition-[color,box-shadow,border-color]",
        "placeholder:text-muted-foreground/70 selection:bg-primary/30",
        "file:inline-flex file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        "focus-visible:border-[color-mix(in_oklch,var(--primary)_55%,var(--input))] focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/30",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
