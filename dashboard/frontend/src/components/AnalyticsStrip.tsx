import { CheckCircle2, Layers, MessageCircleReply, Send } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Overview } from "../api";
import { pct } from "../lib";
import { Card } from "./ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";

function Metric({
  label,
  value,
  sub,
  tone,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  icon: LucideIcon;
  highlight?: boolean;
}) {
  return (
    <Card className="relative overflow-hidden p-4">
      {highlight && (
        <div
          className="absolute inset-x-0 top-0 h-0.5"
          style={{ background: "linear-gradient(90deg, var(--primary), var(--accent2))" }}
        />
      )}
      <div className="flex items-center justify-between">
        <div className="text-caption text-muted-foreground uppercase">{label}</div>
        <Icon className="size-4 text-muted-foreground/60" />
      </div>
      <div className="mt-1.5 text-3xl font-semibold tabular-nums" style={{ color: tone }}>
        {value}
      </div>
      {sub && <div className="mt-0.5 text-[0.72rem] text-muted-foreground">{sub}</div>}
    </Card>
  );
}

export function AnalyticsStrip({ ov }: { ov: Overview }) {
  const inPipeline =
    (ov.counts.shortlisted || 0) +
    (ov.counts.tailored || 0) +
    (ov.counts.ready || 0) +
    (ov.counts.applied || 0) +
    (ov.counts.responded || 0) +
    (ov.counts.interview || 0);

  const rr = ov.response_rate;
  const rrBand =
    rr == null
      ? "aún sin datos"
      : rr >= 0.1
        ? "fuerte (≥10%)"
        : rr >= 0.02
          ? "típico 2–5%"
          : "bajo";

  const max = Math.max(...ov.funnel.map((f) => f.count), 1);

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          label="En pipeline"
          value={String(inPipeline)}
          sub={`${ov.total_jobs} descubiertos`}
          icon={Layers}
        />
        <Metric
          label="Listos para enviar"
          value={String(ov.ready)}
          tone="var(--color-action)"
          sub="revisa y envía"
          icon={Send}
          highlight
        />
        <Metric
          label="Tasa de respuesta"
          value={pct(rr)}
          sub={rrBand}
          tone="var(--color-done)"
          icon={MessageCircleReply}
        />
        <Metric
          label="Aplicaciones"
          value={String(ov.applied)}
          sub={`entrevistas: ${ov.counts.interview || 0}`}
          icon={CheckCircle2}
        />
      </div>
      <Card className="p-4">
        <div className="mb-3 text-caption text-muted-foreground uppercase">Embudo</div>
        <TooltipProvider>
          <div className="flex h-20 items-end gap-2">
            {ov.funnel.map((f) => (
              <Tooltip key={f.stage}>
                <TooltipTrigger asChild>
                  <div className="flex flex-1 cursor-default flex-col items-center gap-1">
                    <div className="text-[0.7rem] tabular-nums text-muted-foreground">
                      {f.count}
                    </div>
                    <div className="flex w-full flex-1 items-end">
                      <div
                        className="w-full rounded-t-md transition-[height] duration-[var(--dur-slow)] ease-[var(--ease-out)]"
                        style={{
                          height: `${Math.max((f.count / max) * 100, 4)}%`,
                          background: "linear-gradient(180deg, var(--chart-1), var(--chart-2))",
                          opacity: 0.6 + 0.4 * (f.count / max),
                          boxShadow:
                            "0 0 16px color-mix(in oklch, var(--chart-1) 22%, transparent)",
                        }}
                      />
                    </div>
                    <div className="w-full truncate text-center text-[0.6rem] text-muted-foreground/70">
                      {f.stage}
                    </div>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <span className="font-medium">{f.stage}</span>: {f.count}
                </TooltipContent>
              </Tooltip>
            ))}
          </div>
        </TooltipProvider>
      </Card>
    </div>
  );
}
