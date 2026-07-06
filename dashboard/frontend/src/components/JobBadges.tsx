import { Globe, Repeat, ShieldAlert } from "lucide-react";
import type { Job } from "../api";
import { Badge } from "./ui/badge";

// Scopes that mean "no restriction" — the geo chip only appears on a real restriction.
const OPEN_SCOPES = ["", "worldwide", "unknown"];

// Both chips ride the warning (amber) token family: per the v2 visual language, --warning is the
// only continuity color from v1 and is exclusively functional — knockouts, geo flags, reposts.

/** Chip for a remote job restricted to a country/region ("Remote — US only"). */
export function GeoBadge({ job }: { job: Job }) {
  const scope = (job.geo_scope || "").trim();
  if (!scope || OPEN_SCOPES.includes(scope)) return null;
  return (
    <Badge
      variant="warning"
      className="px-1.5 py-0 text-[0.62rem] uppercase"
      title={`Remoto con restricción geográfica: ${job.geo_restriction || scope.toUpperCase()}`}
    >
      <Globe className="size-3" /> {scope.split(",")[0]}
    </Badge>
  );
}

/** Chip for a posting the same company re-published ≥1× in 90 días (posible ghost job). */
export function RepostBadge({ job }: { job: Job }) {
  const n = job.repost_count ?? 0;
  if (n < 1) return null;
  return (
    <Badge
      variant="warning"
      className="px-1.5 py-0 text-[0.62rem]"
      title={`Republicado ${n} ${n === 1 ? "vez" : "veces"} en 90 días — posible ghost job`}
    >
      <Repeat className="size-3" /> repost
    </Badge>
  );
}

// F4 Block G: posting-legitimacy tier. tier→variant sigue el lenguaje visual v2 — `low` monta el
// token funcional --warning (misma familia que knockout/geo/repost), `medium` es neutro y `high`
// usa --success. El texto son OBSERVACIONES (nunca acusaciones): el detalle de señales va en el
// title. NULL = sin evaluar → no renderiza nada.
const LEGITIMACY: Record<
  NonNullable<Job["legitimacy_tier"]>,
  { label: string; variant: "warning" | "secondary" | "success" }
> = {
  high: { label: "alta", variant: "success" },
  medium: { label: "media", variant: "secondary" },
  low: { label: "baja", variant: "warning" },
};

/**
 * Chip de legitimidad del posting. En la card (`compact`) solo aparece en tier `low` — la señal
 * que el usuario necesita ver de un vistazo; en el detalle (`compact` off) se muestra cualquier
 * tier con su etiqueta. Las notas van en el `title` (observaciones, nunca acusaciones).
 */
export function LegitimacyBadge({ job, compact = false }: { job: Job; compact?: boolean }) {
  const tier = job.legitimacy_tier;
  if (!tier) return null;
  if (compact && tier !== "low") return null;
  const { label, variant } = LEGITIMACY[tier];
  const notes = job.legitimacy_notes || undefined;
  if (compact) {
    return (
      <Badge variant="warning" className="px-1.5 py-0 text-[0.62rem]" title={notes}>
        <ShieldAlert className="size-3" /> legitimidad baja
      </Badge>
    );
  }
  return (
    <Badge variant={variant} title={notes}>
      <ShieldAlert className="size-3" /> legitimidad: {label}
    </Badge>
  );
}
