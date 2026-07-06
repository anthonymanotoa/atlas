// Única fuente de query keys. Nunca escribir un array-key a mano fuera de aquí.
export const qk = {
  overview: ["overview"] as const,
  board: ["board"] as const,
  job: (id: string) => ["job", id] as const,
  profiles: ["profiles"] as const,
  onboarding: ["onboarding"] as const,
  settings: ["settings"] as const,
  csvColumns: ["csv-columns"] as const,
  cvLibrary: ["cv-library"] as const,
  portfolio: ["portfolio"] as const,
  peers: ["peers"] as const,
  portfolioResearch: ["portfolio-research"] as const,
  intents: ["intents"] as const,
  cvReviews: (jobId: string) => ["cv-reviews", jobId] as const,
  upskill: ["upskill"] as const,
};
