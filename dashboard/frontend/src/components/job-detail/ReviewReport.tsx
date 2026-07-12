import { CircleCheck, CircleAlert } from "lucide-react";
import { Card } from "../ui/card";
import { SectionTitle } from "./SectionTitle";

// Task 12's review.md renders one bullet per deterministic check:
//   "- ✅ **Check name**: detail"  |  "- ⚠️ **Check name** _(informativo)_: detail"
// (see engine/cv/review_report.py::_render_markdown). Parsed here into structured rows
// instead of dumping raw markdown, so it reads like the rest of the UI.
const CHECK_LINE = /^- (✅|⚠️) \*\*(.+?)\*\*(?: _\(informativo\)_)?: (.*)$/;

type ParsedCheck = { ok: boolean; name: string; detail: string; advisory: boolean };

function parseChecks(markdown: string): ParsedCheck[] {
  const out: ParsedCheck[] = [];
  for (const line of markdown.split("\n")) {
    const m = CHECK_LINE.exec(line.trim());
    if (!m) continue;
    out.push({
      ok: m[1] === "✅",
      name: m[2],
      detail: m[3],
      advisory: line.includes("_(informativo)_"),
    });
  }
  return out;
}

// Task 13: la revisión DETERMINISTA (sin LLM) que Task 12 escribe junto a cada CV adaptado.
// Complementa a CvReviewPanel (la revisión del brain, con IntentConfirmDialog para pedirla).
export function ReviewReport({ markdown }: { markdown: string | null }) {
  if (!markdown) return null;
  const checks = parseChecks(markdown);
  if (checks.length === 0) return null;
  return (
    <div>
      <SectionTitle>Revisión determinista del CV</SectionTitle>
      <Card className="space-y-2 p-3.5 text-sm">
        {checks.map((c) => (
          <div key={c.name} className="flex items-start gap-2">
            {c.ok ? (
              <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" />
            ) : (
              <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-warning" />
            )}
            <div>
              <span className="font-medium">{c.name}</span>
              {c.advisory && (
                <span className="ml-1 text-[0.72rem] text-muted-foreground">(informativo)</span>
              )}
              <span className="text-muted-foreground"> — {c.detail}</span>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
