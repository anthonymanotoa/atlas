// Lightweight client-side filters for the board (P1-A): salary disclosed, language, freshness.
// Operates on the already-annotated jobs (salary_visible / language / posted_days), so no
// extra request is needed.

import { SlidersHorizontal } from "lucide-react";
import { Checkbox } from "./ui/checkbox";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export type Filters = { onlySalary: boolean; language: string; maxAgeDays: number };

const AGE_OPTIONS = [
  { value: "0", label: "Frescura: cualquiera" },
  { value: "14", label: "≤ 14 días" },
  { value: "30", label: "≤ 30 días" },
  { value: "60", label: "≤ 60 días" },
  { value: "90", label: "≤ 90 días" },
];

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
    <div className="mb-3 flex flex-wrap items-center gap-2.5 text-[0.8rem] text-muted-foreground">
      <SlidersHorizontal className="size-3.5 text-muted-foreground/70" />
      <Label className="cursor-pointer font-normal text-muted-foreground">
        <Checkbox
          checked={filters.onlySalary}
          onCheckedChange={(c) => setFilters({ ...filters, onlySalary: c === true })}
        />
        Solo con salario
      </Label>
      <Select
        value={filters.language || "all"}
        onValueChange={(v) => setFilters({ ...filters, language: v === "all" ? "" : v })}
      >
        <SelectTrigger size="sm" className="w-auto">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Idioma: todos</SelectItem>
          {languages.map((l) => (
            <SelectItem key={l} value={l}>
              {l.toUpperCase()}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={String(filters.maxAgeDays)}
        onValueChange={(v) => setFilters({ ...filters, maxAgeDays: Number(v) })}
      >
        <SelectTrigger size="sm" className="w-auto">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {AGE_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
