// Typed client for the Atlas FastAPI backend.

export type Job = {
  id: string;
  title: string;
  company: string;
  location?: string;
  is_remote?: number | null;
  workplace_type?: string;
  url?: string;
  apply_url?: string;
  state: string;
  fit_score?: number | null;
  fit_reasons?: string[];
  knockout_flags?: string[];
  sources?: string[];
  discovered_at?: string;
  applied_at?: string | null;
  age_days?: number | null;
  applied_days?: number | null;
  description?: string;
};

export type Action = {
  type: string;
  priority: number;
  job_id: string;
  title: string;
  company: string;
  label: string;
  link?: string;
  contact?: string;
};

export type Overview = {
  total_jobs: number;
  counts: Record<string, number>;
  funnel: { stage: string; count: number }[];
  response_rate: number | null;
  interview_rate: number | null;
  applied: number;
  ready: number;
  last_run?: string;
  last_success?: string;
  downtime_hours?: number | null;
  source_health: { source: string; ok: number; count: number; error?: string }[];
};

export type Message = {
  id: number; kind: string; channel: string; subject?: string; body: string;
  language: string; state: string; variant?: string;
};
export type CvVersion = {
  id: number; language: string; ats_target?: string; path_docx?: string; path_pdf?: string;
  keyword_coverage?: number; matched_keywords?: string; missing_keywords?: string; parse_ok?: number;
};
export type Referral = { id: number; name: string; company?: string; title?: string; linkedin_url?: string };
export type JobDetail = {
  job: Job;
  cv_versions: CvVersion[];
  messages: Message[];
  referrals: Referral[];
  timeline: { stage: string; at: string }[];
};

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
async function post<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const api = {
  overview: () => get<{ overview: Overview; needs_action: Action[] }>("/api/overview"),
  board: () => get<{ columns: string[]; jobs: Record<string, Job[]> }>("/api/board"),
  job: (id: string) => get<JobDetail>(`/api/jobs/${id}`),
  setState: (id: string, state: string) => post(`/api/jobs/${id}/state`, { state }),
  markApplied: (id: string) => post(`/api/jobs/${id}/applied`),
  prep: (id: string, language = "en") => post(`/api/jobs/${id}/prep`, { language }),
  markSent: (mid: number) => post(`/api/messages/${mid}/sent`),
  brief: () => get<{ markdown: string }>("/api/brief"),
  cvDownload: (jobId: string, vid: number) => `/api/cv/${jobId}/${vid}/download`,
};
