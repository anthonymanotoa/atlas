import type { ReactNode } from "react";

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="mb-2 text-caption text-muted-foreground uppercase">{children}</div>;
}
