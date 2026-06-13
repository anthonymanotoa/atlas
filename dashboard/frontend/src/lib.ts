import { clsx, type ClassValue } from "clsx";

export const cn = (...a: ClassValue[]) => clsx(a);

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

export const ACTION_META: Record<string, { icon: string; tone: string }> = {
  ask_referral: { icon: "🤝", tone: "var(--color-accent2)" },
  send_application: { icon: "📨", tone: "var(--color-action)" },
  reply: { icon: "💬", tone: "var(--color-done)" },
  follow_up: { icon: "⏰", tone: "var(--color-pending)" },
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
