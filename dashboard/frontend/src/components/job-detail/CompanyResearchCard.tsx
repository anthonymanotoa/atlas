import type { CompanyResearch } from "../../api";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import { InsightsIcon } from "../ui/icons";
import { SectionTitle } from "./SectionTitle";

// Task 14: company_research intent output (read-only — el brain investiga, nunca envía nada).
export function CompanyResearchCard({ research }: { research: CompanyResearch | null }) {
  if (!research || !research.summary) return null;
  return (
    <div>
      <SectionTitle>
        <span className="inline-flex items-center gap-1.5">
          <InsightsIcon className="size-3.5" /> Sobre la empresa
        </span>
      </SectionTitle>
      <Card className="space-y-2.5 p-3.5 text-sm">
        <p>{research.summary}</p>
        {research.signals.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {research.signals.map((s) => (
              <Badge key={s} variant="outline">
                {s}
              </Badge>
            ))}
          </div>
        )}
        {research.sources.length > 0 && (
          <div className="flex flex-wrap gap-x-2 text-[0.72rem] text-muted-foreground">
            {research.sources.map((src) => (
              <a
                key={src}
                href={src}
                target="_blank"
                rel="noreferrer"
                className="text-primary hover:underline"
              >
                fuente ↗
              </a>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
