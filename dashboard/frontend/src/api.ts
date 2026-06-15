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
export type Profile = { id: string; label: string; is_owner?: boolean };
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
  cv_present: boolean;
  audit: { findings: Finding[]; summary: { high: number; med: number; low: number } };
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
export type JobDetail = {
  job: Job;
  cv_versions: CvVersion[];
  messages: Message[];
  referrals: Referral[];
  social_mentions?: SocialMention[];
  learnings?: Learning[];
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
  exportUrl: (columns?: string[], state?: string) => {
    const p = new URLSearchParams();
    if (columns?.length) p.set("columns", columns.join(","));
    if (state) p.set("state", state);
    const q = p.toString();
    return `/api/export${q ? `?${q}` : ""}`;
  },
};
