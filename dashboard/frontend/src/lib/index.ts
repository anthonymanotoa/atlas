// Atlas domain helpers + the shared `cn` class merger.
// `cn` lives in ./utils (twMerge-backed) and is re-exported here so existing
// `import { cn } from "../lib"` call sites keep working unchanged.
export { cn } from "./utils";

export const STATE_ES: Record<string, string> = {
  discovered: "Descubierto",
  scored: "Evaluado",
  shortlisted: "Preseleccionado",
  tailored: "CV listo",
  drafted: "Borradores",
  ready: "Listo para enviar",
  applied: "Aplicado",
  responded: "Respondió",
  interview: "Entrevista",
  offer: "Oferta",
  rejected: "Rechazado",
  closed: "Cerrado",
};

export const COLUMN_ES: Record<string, string> = {
  shortlisted: "Preseleccionados",
  tailored: "CV listo",
  ready: "Listos para enviar",
  applied: "Aplicados",
  responded: "Respondieron",
  interview: "Entrevista",
  offer: "Oferta",
};

// Tone per action type (the icon now lives in the lucide icon map — see components/ui/icons.ts).
export const ACTION_META: Record<string, { tone: string }> = {
  ask_referral: { tone: "var(--color-accent2)" },
  send_application: { tone: "var(--color-action)" },
  reply: { tone: "var(--color-done)" },
  follow_up: { tone: "var(--color-pending)" },
};

export function fitTone(score?: number | null): string {
  if (score == null) return "var(--color-faint)";
  if (score >= 85) return "var(--color-done)";
  if (score >= 65) return "var(--color-accent)";
  return "var(--color-muted)";
}

export function ageLabel(days?: number | null): string {
  if (days == null) return "";
  if (days < 1) return "hoy";
  if (days < 2) return "1d";
  return `${Math.round(days)}d`;
}

// "publicado hace X" from the vacancy's own posting date (requisito #4).
export function freshLabel(days?: number | null): string {
  if (days == null) return "";
  if (days < 1) return "publicado hoy";
  if (days < 30) return `publicado hace ${Math.round(days)}d`;
  const m = Math.round(days / 30);
  return `publicado hace ${m} ${m === 1 ? "mes" : "meses"}`;
}

const _CUR_SYM: Record<string, string> = { USD: "$", EUR: "€", GBP: "£" };

// Compact salary range, e.g. "$120k–$160k/año". Null when no salary is disclosed.
export function salaryLabel(job: {
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  salary_interval?: string | null;
}): string | null {
  const lo = job.salary_min ?? null;
  const hi = job.salary_max ?? null;
  if (lo == null && hi == null) return null;
  const sym = job.salary_currency
    ? (_CUR_SYM[job.salary_currency] ?? `${job.salary_currency} `)
    : "";
  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : `${Math.round(n)}`);
  const range = lo != null && hi != null ? `${fmt(lo)}–${fmt(hi)}` : fmt((hi ?? lo) as number);
  const per =
    job.salary_interval === "yearly"
      ? "/año"
      : job.salary_interval === "monthly"
        ? "/mes"
        : job.salary_interval === "hourly"
          ? "/h"
          : "";
  return `${sym}${range}${per}`;
}

export function langLabel(code?: string | null): string {
  return code ? code.toUpperCase() : "";
}

export async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    /* ignore */
  }
}

export function pct(v?: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}
