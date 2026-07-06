import { Globe, Repeat } from "lucide-react";
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
