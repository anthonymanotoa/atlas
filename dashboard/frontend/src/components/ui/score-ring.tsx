import { cn } from "@/lib/utils";

// Conic-gradient progress ring colored by a caller-provided tone (e.g. fitTone()).
// Dependency-free; the center disc inherits the surface via `centerClassName`.
export function ScoreRing({
  value,
  tone,
  size = 38,
  centerClassName = "bg-card",
  className,
}: {
  value?: number | null;
  tone: string;
  size?: number;
  centerClassName?: string;
  className?: string;
}) {
  const pctv = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <div
        className="absolute inset-0 rounded-full"
        style={{ background: `conic-gradient(${tone} ${pctv}%, var(--border) 0)` }}
      />
      <div
        className={cn(
          "absolute inset-[3px] grid place-items-center rounded-full text-[0.72rem] font-semibold tabular-nums",
          centerClassName,
        )}
        style={{ color: tone }}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}
