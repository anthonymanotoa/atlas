---
name: atlas-design-system
description: >-
  Apply the Atlas "Warm Editorial" design system to ANY visual/UI work in this repo
  (the dashboard/frontend React app). ALWAYS use this whenever building, creating, making,
  designing, styling, restyling, or tweaking a component, page, screen, dashboard, board,
  card, drawer/sheet, modal/dialog, form, button, badge, chip, table, chart, tooltip, menu,
  toast, or any UI — and whenever editing dashboard/frontend/src/**, src/components/ui/**,
  or src/index.css. Ensures every change is brand-consistent (warm charcoal + amber/terracotta,
  Geist, the shared primitives and tokens) without re-specifying colors or styles.
---

# Atlas Design System (enforcement skill)

The canonical spec is **`dashboard/frontend/DESIGN_SYSTEM.md`** — read it before any visual change.
This skill exists to make sure UI work in this repo follows it.

## Sources of truth (read / reuse these — don't reinvent)
- **`dashboard/frontend/DESIGN_SYSTEM.md`** — tokens, type scale, elevation, motion, patterns.
- **`dashboard/frontend/src/components/ui/*`** — the primitives (Button, Input, Select, Checkbox,
  Switch, Badge, Card, Dialog, Sheet, Tooltip, Tabs, ScrollArea, Separator, Skeleton, Sonner,
  Command, Kbd, ScoreRing). Compose from these; do not hand-roll equivalents.
- **`dashboard/frontend/src/components/ui/icons.ts`** — the only place icons are declared. No raw emoji.
- **`dashboard/frontend/src/index.css`** — the token system (`@theme inline` + `[data-theme]`).

## Non-negotiable rules
1. **Use semantic tokens / Tailwind utilities** (`bg-card`, `text-muted-foreground`, `border-border`,
   `bg-primary`, `text-primary`, `bg-secondary`, `bg-success/warning/info/destructive`, `ring-ring`)
   or `var(--token)`. Never hardcode hex/raw colors.
2. **Never use `bg-accent` / `text-accent-foreground` / `bg-muted`** — they're intentionally unmapped.
   Use `secondary` for hover washes/surfaces and `text-muted-foreground` for muted text.
3. **Theme = `data-theme` on `<html>`** (dark/light). Never add a `.dark` class or change the switch.
4. **Typography:** Geist; use `text-display/h1/h2/h3/caption`, `font-mono` for code, and `tabular-nums`
   on all numbers.
5. **No raw emoji** — add to `icons.ts` and import from there.
6. **`cn` from `@/lib/utils`**; `@/` → `src/`.
7. **Motion:** Radix anims via `tw-animate-css`; respect `prefers-reduced-motion`; never animate a
   dnd-kit dragged node or put `backdrop-filter`/`filter` on a draggable ancestor.

## Invariants
- **Visual only** unless the task is explicitly about logic — keep handlers, API (`src/api.ts`), props,
  state, and data flow intact.
- Keep **Spanish** user-facing strings (some are asserted by tests).
- Lint runs `--max-warnings 0`; build is separate from `check.sh`.

## After any UI change, verify
```bash
npm --prefix dashboard/frontend run lint
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
```

Adding a new shadcn component is fine (`components.json` is set up), but re-theme it to the tokens
above and **revert any CLI edits to `src/index.css`**.
