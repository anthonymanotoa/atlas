import type * as React from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

// Theme is passed explicitly from App state (which mirrors the [data-theme] attribute),
// since sonner's default `theme="system"` would ignore our runtime attribute switch.
function Toaster({ theme = "dark", ...props }: ToasterProps) {
  return (
    <Sonner
      theme={theme}
      className="toaster group"
      position="bottom-right"
      richColors
      toastOptions={{
        style: {
          background: "var(--popover)",
          color: "var(--popover-foreground)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          boxShadow: "var(--shadow-lg), var(--highlight-top)",
        },
      }}
      style={{ "--toast-z-index": "100" } as React.CSSProperties}
      {...props}
    />
  );
}

export { Toaster };
