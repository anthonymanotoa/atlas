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
  source?: string; // first source that discovered it (raw row column)
  discovered_at?: string;
  applied_at?: string | null;
  age_days?: number | null;
  applied_days?: number | null;
  description?: string;
  // P1-A quality-gate fields (additive; backend may omit on older rows)
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  salary_interval?: string | null;
  language?: string | null;
  posted_days?: number | null;
  salary_visible?: boolean;
  // CV↔JD match (distinct from fit_score): how well the master CV covers the posting.
  match_score?: number | null;
  missing_keywords?: string[]; // importance-ranked JD keywords the CV doesn't evidence (detail only)
  jd_skills?: string[]; // skills the posting itself asks for, extracted from the description (detail only)
  // F2 geo-scoring + hygiene (additive; backend may omit on older rows)
  geo_restriction?: string | null; // raw restriction text ("Remote — US only")
  geo_scope?: string | null; // normalized: iso2/region tokens | "worldwide" | "unknown" | ""
  repost_count?: number | null; // ≥1 = same company re-posted this role in 90 days
  // F4 Block G posting-legitimacy (ghost-job triage; orthogonal to fit/match). NULL = sin evaluar.
  legitimacy_tier?: "high" | "medium" | "low" | null;
  legitimacy_notes?: string | null; // señales observadas, nunca acusaciones
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
  id: number;
  kind: string;
  channel: string;
  subject?: string;
  body: string;
  language: string;
  state: string;
  variant?: string;
};
export type CvVersion = {
  id: number;
  language: string;
  ats_target?: string;
  path_docx?: string;
  path_pdf?: string;
  keyword_coverage?: number;
  matched_keywords?: string;
  missing_keywords?: string;
  parse_ok?: number;
};
export type Referral = {
  id: number;
  name: string;
  company?: string;
  title?: string;
  linkedin_url?: string;
};
export type Profile = { id: string; label: string; domain?: string; is_owner?: boolean };
export type CsvColumn = { id: string; label: string };
export type SocialMention = {
  id: number;
  platform: string;
  source_url?: string;
  recruiter_name?: string;
  recruiter_linkedin?: string;
  recruiter_email?: string;
  post_title?: string;
  post_excerpt?: string;
  context_type?: string;
  found_at?: string;
};
export type Finding = { severity: string; area: string; message: string; suggestion: string };
export type OnboardingStatus = {
  complete: boolean;
  profile: string;
  // Domain context so the UI can phrase copy per-industry instead of hardcoding "AI/ML".
  // `target_label` is the repositioning target / CV headline; empty → use neutral phrasing.
  domain?: string;
  target_label?: string;
  cv_present: boolean;
  audit: { findings: Finding[]; summary: { high: number; med: number; low: number } };
};
// Frontmatter of the active profile's criteria.md (GET/PUT /api/criteria). Only the fields
// the wizard edits are typed; everything else round-trips untouched via the index signature.
export type CriteriaConfig = {
  roles: string[];
  role_aliases: string[];
  seniority: string[];
  remote_required: boolean;
  onsite_locations: string[];
  languages: string[];
  salary_floor_usd: number;
  candidate_years: number;
  candidate_country: string;
  acceptable_regions: string[];
  geo_penalty: number;
  re_apply_window_days: number;
  shortlist_threshold: number;
  [key: string]: unknown;
};
export type Interviewer = {
  id: number;
  name: string;
  title?: string;
  company?: string;
  linkedin_url?: string;
  research_notes?: string;
};
export type Interview = {
  id: number;
  job_id: string;
  scheduled_at?: string;
  round?: string;
  mode?: string;
  status?: string;
  prep_path?: string;
  deep_prep_md?: string | null;
  debrief_md?: string | null;
  interviewers?: Interviewer[];
};
export type Learning = {
  id: number;
  company: string;
  pattern_type: string;
  observation: string;
  confidence: number;
  evidence_count: number;
};
export type Portfolio = { id: number; version: string; path_html?: string; generated_at?: string };
export type PeerExample = {
  peer_name: string;
  url: string;
  role_match: string;
  key_strengths: string[];
  what_to_steal: string[];
};
export type PortfolioResearch = {
  examples: PeerExample[];
  patterns: Record<string, string[]>;
  prompt: string;
};
export type Peer = {
  id: number;
  peer_name: string;
  role_match?: string;
  peer_profile_url?: string;
  peer_portfolio_url?: string;
  key_strengths?: string[];
  how_to_emulate?: string[];
  source_url?: string;
  notes?: string;
};
// F4 §7.1 intents queue — la web SOLO encola ($0); el brain drena la cola y ejecuta el LLM.
// El status refleja el ciclo de vida server-side (pending → running → done|error).
export type Intent = {
  id: string;
  type: string;
  job_id?: string | null;
  payload?: Record<string, unknown>;
  status: "pending" | "running" | "done" | "error";
  result_ref?: string | null;
  error?: string | null;
  created_at: string;
  completed_at?: string | null;
};

// F4 §7.2 cv_review — el reviewer LLM (hiring-manager proxy) devuelve edits mecánicos +
// crítica en 4 categorías + flags del backtrack test. La web aplica edits uno a uno y resuelve
// flags keep/soften/drop; TODO el trabajo LLM lo hizo el brain — estos endpoints son deterministas.
export type CvReviewEdit = {
  file: string;
  old_string: string;
  new_string: string;
  reason: string;
  applied?: boolean;
  applied_ref?: string;
};
export type CvReviewFlag = {
  file: string;
  bullet: string;
  classification: "OK" | "Flag" | "Never";
  reason: string;
  softened?: string;
  resolution?: "keep" | "soften" | "drop";
};
export type CvReview = {
  id: number;
  job_id: string;
  cv_version_id?: number | null;
  edits: CvReviewEdit[];
  critique: Record<string, string[]>;
  flags: CvReviewFlag[];
  created_at: string;
};

// F4 §7.2 upskill_report — análisis de brechas en dos pasadas: (1) diff duro de skills
// (determinista, engine.upskill.hard_skill_gaps) + (2) síntesis del brain (report_md + heatmap).
// La web solo LEE el reporte persistido; el trabajo LLM lo hizo el brain offline ($0).
export type UpskillHeatItem = {
  skill: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  note: string;
};
export type UpskillReport = {
  id: number;
  report_md: string;
  heatmap: UpskillHeatItem[];
  hard_gaps: { skills?: { skill: string; score: number; occurrences: number }[] };
  created_at: string;
};

export type JobDetail = {
  job: Job;
  cv_versions: CvVersion[];
  messages: Message[];
  referrals: Referral[];
  social_mentions?: SocialMention[];
  learnings?: Learning[];
  timeline: { stage: string; at: string }[];
};

// F3 §6.5 ops: system health + resolve/add company + reverse discovery.
export type SystemHealth = {
  profile: string;
  db: { path: string; ok: boolean; jobs: number };
  counts: Record<string, number>;
  last_run: string | null;
  last_success: string | null;
  sources: {
    source: string;
    ok: boolean;
    count: number;
    run_at: string | null;
    error: string | null;
  }[];
  safeguards: { api_key_unset: boolean; base_url_default: boolean };
};

export type ResolvedCompany = {
  resolved: boolean;
  company: string | null;
  ats: string | null;
  token: string | null;
  preview_jobs_count: number;
  already_configured: boolean;
};

export type CompanySuggestion = {
  company: string;
  ats: string;
  token: string;
  jobs_count: number;
  matching_titles: string[];
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
async function put<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
// Multipart upload: never set Content-Type — the browser adds it WITH the boundary.
async function postForm<T>(url: string, form: FormData): Promise<T> {
  const r = await fetch(url, { method: "POST", body: form });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

export const api = {
  overview: () => get<{ overview: Overview; needs_action: Action[] }>("/api/overview"),
  board: () =>
    get<{ columns: string[]; jobs: Record<string, Job[]>; dismissed: Job[] }>("/api/board"),
  job: (id: string) => get<JobDetail>(`/api/jobs/${id}`),
  setState: (id: string, state: string) => post(`/api/jobs/${id}/state`, { state }),
  markApplied: (id: string) => post(`/api/jobs/${id}/applied`),
  // language omitted → backend auto-picks the posting's language (es offers → ES CV, else EN)
  prep: (id: string, language?: string) =>
    post<{ ok: boolean; coverage: number; parse_ok: boolean; language: string }>(
      `/api/jobs/${id}/prep`,
      language ? { language } : {},
    ),
  markSent: (mid: number) => post(`/api/messages/${mid}/sent`),
  discover: () => post<{ started: boolean; running?: boolean }>("/api/discover"),
  discoverStatus: () => get<{ running: boolean }>("/api/discover/status"),
  brief: () => get<{ markdown: string }>("/api/brief"),
  cvDownload: (jobId: string, vid: number, fmt = "docx") =>
    `/api/cv/${jobId}/${vid}/download?fmt=${fmt}`,
  cvLibrary: () =>
    get<{ dir: string; count: number; files: { name: string; size: number; modified: number }[] }>(
      "/api/cv/library",
    ),
  profiles: () => get<{ profiles: Profile[]; active: string }>("/api/profiles"),
  switchProfile: (id: string) => post<{ ok: boolean; active: string }>("/api/profile", { id }),
  renameProfile: (id: string, label: string) =>
    post<{ ok: boolean; id: string; label: string }>(`/api/profiles/${id}/label`, { label }),
  // settings + CSV export (P1-B)
  settings: () => get<Record<string, string | null>>("/api/settings"),
  setSetting: (key: string, value: string) =>
    post<{ ok: boolean; key: string; value: string }>("/api/settings", { key, value }),
  csvColumns: () => get<{ available: CsvColumn[]; selected: string[] }>("/api/csv/columns"),
  onboarding: () => get<OnboardingStatus>("/api/onboarding"),
  completeOnboarding: () => post<{ ok: boolean }>("/api/onboarding/complete"),
  cvAudit: () =>
    get<{
      cv_present: boolean;
      audit: { findings: Finding[]; summary: { high: number; med: number; low: number } };
    }>("/api/cv/audit"),
  recordOutcome: (
    id: string,
    body: {
      final_state: string;
      response_days?: number | null;
      interview_count?: number;
      offer_made?: boolean;
      recruiter_source?: string | null;
      reason?: string | null;
    },
  ) => post<{ ok: boolean; learnings: Learning[] }>(`/api/jobs/${id}/outcome`, body),
  learnings: (company?: string) =>
    get<{ learnings: Learning[] }>(
      `/api/learnings${company ? `?company=${encodeURIComponent(company)}` : ""}`,
    ),
  interviews: (jobId: string) => get<{ interviews: Interview[] }>(`/api/jobs/${jobId}/interviews`),
  addInterview: (
    jobId: string,
    body: { scheduled_at?: string; round?: string; mode?: string; notes?: string },
  ) => post<{ ok: boolean; id: number }>(`/api/jobs/${jobId}/interview`, body),
  addInterviewer: (interviewId: number, body: Partial<Interviewer>) =>
    post<{ ok: boolean; id: number }>(`/api/interview/${interviewId}/interviewer`, body),
  genPrep: (interviewId: number, language = "en") =>
    post<{ ok: boolean; path: string; markdown: string }>(`/api/interview/${interviewId}/prep`, {
      language,
    }),
  // F4 §7.2 interview_prep_deep: encolar el prep profundo (Audience Map + preguntas citadas +
  // historias) y guardar el debrief post-entrevista (opcionalmente re-encola el prep). Ninguna
  // corre un LLM: el brain lo hace offline ($0).
  enqueueInterviewPrepDeep: (interviewId: number, jobId: string) =>
    api.enqueueIntent("interview_prep_deep", { interview_id: interviewId }, jobId),
  interviewDebrief: (interviewId: number, debriefMd: string, reanalyze: boolean) =>
    post<{ ok: boolean; intent_id: string | null }>(`/api/interview/${interviewId}/debrief`, {
      debrief_md: debriefMd,
      reanalyze,
    }),
  socialMentions: (id: string) =>
    get<{ mentions: SocialMention[] }>(`/api/jobs/${id}/social_mentions`),
  startSocialSearch: (id: string) =>
    post<{ ok: boolean; queries: Record<string, string> }>(`/api/jobs/${id}/start-social-search`),
  addSocialMention: (id: string, body: Partial<SocialMention>) =>
    post<{ ok: boolean; id: number }>(`/api/jobs/${id}/social_mentions`, body),
  portfolioLatest: () => get<{ portfolio: Portfolio | null }>("/api/portfolio/latest"),
  generatePortfolio: (include_github = false) =>
    post<{ ok: boolean; id: number; version: string; path: string }>("/api/portfolio/generate", {
      include_github,
    }),
  portfolioPreviewUrl: (id: number) => `/api/portfolio/${id}/preview`,
  portfolioResearch: () => get<PortfolioResearch>("/api/portfolio/research"),
  peers: () => get<{ peers: Peer[] }>("/api/peers"),
  addPeer: (body: Partial<Peer>) => post<{ ok: boolean; id: number }>("/api/peers", body),
  // F2: onboarding wizard + hygiene
  criteria: () => get<{ criteria: CriteriaConfig; prose: string }>("/api/criteria"),
  saveCriteria: (criteria: CriteriaConfig, prose: string) =>
    put<{ ok: boolean; path: string }>("/api/criteria", { criteria, prose }),
  importCv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<{ ok: boolean; draft: string; path: string; chars: number }>(
      "/api/cv/import",
      form,
    );
  },
  livenessSweep: () => post<{ started: boolean; running?: boolean }>("/api/liveness/sweep"),
  // F3 §6.5: expose CLI-only ops (system health, resolve/add company, reverse discovery, import).
  systemHealth: () => get<SystemHealth>("/api/system/health"),
  resolveCompany: (url: string) => post<ResolvedCompany>("/api/companies/resolve", { url }),
  addCompany: (entry: { company: string; ats: string; token?: string | null }) =>
    post<{ ok: boolean; added: boolean }>("/api/companies/add", entry),
  suggestCompanies: (names?: string[]) =>
    post<{ suggestions: CompanySuggestion[] }>("/api/discovery/suggest", { names: names ?? [] }),
  importConnections: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<{ ok: boolean; imported: number }>("/api/connections/import", form);
  },
  // F4 §7.1: intents queue. `intents` lista la cola + conteo de pendientes; `enqueueIntent`
  // escribe una fila `pending` (jamás llama a un LLM — eso lo hace el brain offline, $0).
  intents: (status?: string) =>
    get<{ intents: Intent[]; pending: number }>(`/api/intents${status ? `?status=${status}` : ""}`),
  enqueueIntent: (type: string, payload?: Record<string, unknown>, jobId?: string) =>
    post<{ ok: boolean; id: string }>("/api/intents", {
      type,
      job_id: jobId,
      payload: payload ?? {},
    }),
  // F4 §7.2 cv_review: leer las revisiones de una vacante, aplicar un edit mecánico (re-renderiza
  // el CV) y resolver un flag (keep/soften/drop). Ninguna llama a un LLM.
  cvReviews: (jobId: string) => get<{ reviews: CvReview[] }>(`/api/jobs/${jobId}/cv-reviews`),
  applyCvReviewEdit: (id: number, index: number) =>
    post<{ ok: boolean; applied_ref?: string }>(`/api/cv-reviews/${id}/apply-edit`, { index }),
  resolveCvReviewFlag: (id: number, index: number, action: "keep" | "soften" | "drop") =>
    post<{ ok: boolean; resolution: string }>(`/api/cv-reviews/${id}/resolve-flag`, {
      index,
      action,
    }),
  // F4 §7.2 upskill_report: lee el último reporte de brechas (read-only, $0 — la síntesis la
  // hizo el brain offline; la pasada 1 determinista se persiste junto al plan para auditoría).
  upskillLatest: () => get<{ report: UpskillReport | null }>("/api/upskill/latest"),
  exportUrl: (columns?: string[], state?: string) => {
    const p = new URLSearchParams();
    if (columns?.length) p.set("columns", columns.join(","));
    if (state) p.set("state", state);
    const q = p.toString();
    return `/api/export${q ? `?${q}` : ""}`;
  },
};
