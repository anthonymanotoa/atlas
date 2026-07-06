import type { Learning } from "../../api";
import { Card } from "../ui/card";
import { InsightsIcon } from "../ui/icons";
import { SectionTitle } from "./SectionTitle";

export function CompanyInsights({ learnings }: { learnings?: Learning[] }) {
  if (!learnings || learnings.length === 0) return null;
  return (
    <div>
      <SectionTitle>
        <span className="inline-flex items-center gap-1.5">
          <InsightsIcon className="size-3.5" /> Lo aprendido de esta empresa
        </span>
      </SectionTitle>
      <Card className="space-y-1.5 p-3.5 text-sm">
        {learnings.map((l) => (
          <div key={l.id}>
            {l.observation}{" "}
            <span className="text-[0.72rem] text-muted-foreground">
              · confianza {Math.round(l.confidence * 100)}%
            </span>
          </div>
        ))}
      </Card>
    </div>
  );
}
