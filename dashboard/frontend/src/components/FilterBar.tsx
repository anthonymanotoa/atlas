// Lightweight client-side filters for the board (P1-A): salary disclosed, language, freshness.
// Operates on the already-annotated jobs (salary_visible / language / posted_days), so no
// extra request is needed.

export type Filters = { onlySalary: boolean; language: string; maxAgeDays: number };

export function FilterBar({
  filters,
  setFilters,
  languages,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  languages: string[];
}) {
  return (
    <div className="flex items-center gap-2 mb-2 text-[0.78rem] flex-wrap text-[var(--color-muted)]">
      <label className="flex items-center gap-1.5 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={filters.onlySalary}
          onChange={(e) => setFilters({ ...filters, onlySalary: e.target.checked })}
        />
        Solo con salario
      </label>
      <select
        className="btn !py-1 cursor-pointer"
        value={filters.language}
        onChange={(e) => setFilters({ ...filters, language: e.target.value })}
      >
        <option value="">Idioma: todos</option>
        {languages.map((l) => (
          <option key={l} value={l}>
            {l.toUpperCase()}
          </option>
        ))}
      </select>
      <select
        className="btn !py-1 cursor-pointer"
        value={filters.maxAgeDays}
        onChange={(e) => setFilters({ ...filters, maxAgeDays: Number(e.target.value) })}
      >
        <option value={0}>Frescura: cualquiera</option>
        <option value={14}>≤ 14 días</option>
        <option value={30}>≤ 30 días</option>
        <option value={60}>≤ 60 días</option>
        <option value={90}>≤ 90 días</option>
      </select>
    </div>
  );
}
