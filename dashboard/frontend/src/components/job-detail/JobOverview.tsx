import {
  Briefcase,
  CalendarClock,
  FileText,
  Globe,
  Languages,
  ListChecks,
  MapPin,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { JobDetail } from "../../api";
import {
  countryLabel,
  freshLabel,
  langLabel,
  salaryLabel,
  stripHtml,
  workplaceLabel,
} from "../../lib";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";

// "Sobre el puesto": everything the user wants to see BEFORE deciding to apply —
// país, modalidad, salario, responsabilidades y habilidades — without leaving Atlas.
function InfoItem({
  icon,
  label,
  value,
  highlight,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <div className="min-w-0">
        <div className="text-[0.68rem] tracking-wide text-muted-foreground uppercase">{label}</div>
        <div
          className={`text-sm ${highlight ? "font-semibold text-foreground" : "text-foreground/90"}`}
        >
          {value || <span className="text-muted-foreground">—</span>}
        </div>
      </div>
    </div>
  );
}

export function JobOverview({ job }: { job: JobDetail["job"] }) {
  const [expanded, setExpanded] = useState(false);
  const desc = stripHtml(job.description);
  const country = countryLabel(job.location);
  const modality = workplaceLabel(job);
  const salary = salaryLabel(job);
  const skills = job.jd_skills || [];
  const LONG = 520;
  const shownDesc = expanded || desc.length <= LONG ? desc : `${desc.slice(0, LONG).trimEnd()}…`;

  return (
    <Card className="space-y-4 p-4">
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <InfoItem
          icon={<MapPin className="size-4" />}
          label="País / ubicación"
          value={country || job.location}
          highlight
        />
        <InfoItem
          icon={<Globe className="size-4" />}
          label="Modalidad"
          value={modality}
          highlight={modality === "Remoto"}
        />
        <InfoItem
          icon={<Wallet className="size-4" />}
          label="Salario"
          value={salary || <span className="text-muted-foreground">No publicado</span>}
          highlight={!!salary}
        />
        <InfoItem
          icon={<Languages className="size-4" />}
          label="Idioma de la oferta"
          value={job.language ? langLabel(job.language) : ""}
        />
        <InfoItem
          icon={<CalendarClock className="size-4" />}
          label="Publicada"
          value={freshLabel(job.posted_days ?? job.age_days) || ""}
        />
        <InfoItem
          icon={<Briefcase className="size-4" />}
          label="Fuente"
          value={(job.sources || []).join(", ") || job.source}
        />
      </div>

      {skills.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[0.68rem] tracking-wide text-muted-foreground uppercase">
            <ListChecks className="size-3.5" /> Habilidades que pide la oferta
          </div>
          <div className="flex flex-wrap gap-1.5">
            {skills.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-[0.68rem] tracking-wide text-muted-foreground uppercase">
          <FileText className="size-3.5" /> Responsabilidades y descripción
        </div>
        {desc ? (
          <>
            <p className="text-[0.82rem] leading-relaxed whitespace-pre-wrap text-foreground/90">
              {shownDesc}
            </p>
            {desc.length > LONG && (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="mt-1.5 text-xs font-medium text-primary hover:underline"
              >
                {expanded ? "Ver menos" : "Ver descripción completa"}
              </button>
            )}
          </>
        ) : (
          <p className="text-[0.82rem] text-muted-foreground">
            Esta fuente no incluyó la descripción.{" "}
            {(job.apply_url || job.url) && (
              <a
                href={job.apply_url || job.url}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                Ábrela en la oferta original ↗
              </a>
            )}
          </p>
        )}
      </div>
    </Card>
  );
}
