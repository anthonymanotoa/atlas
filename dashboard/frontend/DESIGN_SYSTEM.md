# Atlas Design System — "Warm Editorial"

This is the binding visual spec for the Atlas dashboard (`dashboard/frontend/`). **Every UI change
must follow it.** It is enforced two ways: the canonical tokens/primitives live in code
(`src/index.css` + `src/components/ui/*`), and a Claude skill
(`.claude/skills/atlas-design-system/`) + `components.json` route AI changes back here.

> **Golden rule:** compose from `src/components/ui/*` primitives and the semantic tokens below.
> Don't hand-roll buttons/inputs/badges or hardcode hex colors.

---

## 1. Philosophy

Warm, editorial, crafted — not neon. A warm charcoal/ink canvas with a soft amber aurora,
amber→terracotta accent, hairline-bordered surfaces, generous spacing, Geist typography with
tabular numerals, soft elevation, and tasteful motion. References: Linear/Vercel/Mercury calm,
recolored warm. Dark-first; a warm-paper light theme is a first-class peer.

## 2. Theming — `[data-theme]`, never `.dark`

The theme is an attribute on `<html>`: `data-theme="dark" | "light"`, set in `App.tsx` and
`main.tsx` (before first paint). The Tailwind `dark:` variant is wired to it in `index.css`:

```css
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));
```

**Do not** introduce shadcn's default `.dark` class or change this mechanism. New theme-dependent
styles should use semantic tokens (which already flip per theme) — you rarely need `dark:` at all.

## 3. Tokens (`src/index.css`)

Defined as OKLCH custom properties on `:root` (dark) and `:root[data-theme="light"]` (light), then
exposed to Tailwind via `@theme inline` as `bg-*/text-*/border-*` utilities. Use the **utilities**
(`bg-card`, `text-muted-foreground`, `border-border`, `ring-ring`, …) or `var(--token)` — never raw colors.

| Token | Utility | Dark | Light | Use |
|---|---|---|---|---|
| `--background` | `bg-background` | warm charcoal | warm cream | page canvas |
| `--foreground` | `text-foreground` | warm cream | espresso ink | body text |
| `--card` | `bg-card` | raised charcoal | white | cards, board cards |
| `--popover` | `bg-popover` | floating charcoal | white | dialogs, menus, palette |
| `--primary` | `bg-primary` / `text-primary` | amber | burnt amber | brand accent, primary buttons |
| `--primary-foreground` | `text-primary-foreground` | dark ink | near-white | text on amber |
| `--secondary` | `bg-secondary` | neutral surface | warm gray | secondary buttons, hovers, chips |
| `--muted-foreground` | `text-muted-foreground` | warm gray | warm gray | captions, sub-text |
| `--accent2` | `var(--accent2)` | terracotta | terracotta | gradient partner (logo, funnel, referral) |
| `--success` | `bg-success`/`text-success` | green | green | done / positive |
| `--warning` | `bg-warning`/`text-warning` | gold | amber-brown | pending / caution |
| `--info` | `bg-info`/`text-info` | cool azure | blue | informational / "ready" KPI tone |
| `--destructive` | `bg-destructive`/`text-destructive` | red | red | danger / high-severity |
| `--border` | `border-border` | hairline | hairline | all borders |
| `--input` | `border-input` | field border | field border | form field borders |
| `--ring` | `ring-ring` | amber α | amber α | focus rings |
| `--chart-1..5` | `bg-chart-N` | amber/terracotta/gold/green/azure | darker set | funnel & charts |

### ⚠️ Naming rules (don't break these)
- `accent`, `accent-foreground`, and the `muted` **surface** are intentionally **NOT** mapped in
  `@theme`. **Never use `bg-accent` / `text-accent-foreground` / `bg-muted` utilities** — use
  `secondary` for hover washes/surfaces and `text-muted-foreground` for muted text. This frees the
  legacy `--color-accent` / `--color-muted` names to be a clean compat layer.
- **Legacy `--color-*` compat layer:** the original token names (`--color-bg`, `--color-panel`,
  `--color-accent`, `--color-done`, `--color-faint`, …) are re-pointed at the new tokens under
  `:root:root`. They still work, but **new code should prefer the semantic utilities above.**

## 4. Typography — Geist

Self-hosted via `@fontsource-variable/geist` + `geist-mono` (imported in `main.tsx`). `--font-sans`
= Geist Variable, `--font-mono` = Geist Mono Variable. Scale (Tailwind text utilities):

| Class | Size / weight | Use |
|---|---|---|
| `text-display` | 2.25rem / 700 / -0.022em | onboarding hero, empty-state headline |
| `text-h1` | 1.5rem / 650 | drawer/sheet title |
| `text-h2` | 1.125rem / 600 | dialog titles |
| `text-h3` | 0.95rem / 600 | card titles |
| `text-caption` | 0.7rem / 500 / uppercase | metric/section labels, column headers |
| `font-mono` | Geist Mono | code, message/prep bodies, paths |

**Always use `tabular-nums`** on numbers that align or update live (metrics, scores, %, salary,
funnel counts).

## 5. Elevation · radius · motion

- **Shadows:** `var(--shadow-xs|sm|md|lg)`, `var(--shadow-glow)` (amber), `var(--highlight-top)`
  (inset top hairline for the "glass" edge). Cards = `--shadow-sm` + `--highlight-top`; floating
  surfaces (sheet/dialog/popover/command) = `--shadow-lg` + blur.
- **Radius:** `rounded-md` (controls), `rounded-lg` (menus), `rounded-xl` (cards), `rounded-full`
  (badges/avatars). Driven by `--radius` (0.875rem) → `--radius-sm/md/lg/xl`.
- **Motion:** `var(--ease-out)` + `var(--dur-fast|base|slow)`. Radix enter/exit via `tw-animate-css`
  (`animate-in`, `fade-in-0`, `slide-in-from-*`, `zoom-in-95`). Entrance via `.fade-up`. A global
  `prefers-reduced-motion` guard neutralizes animation. **Never animate a dnd-kit dragged node's
  transform**, and never put `backdrop-filter`/`filter` on a draggable ancestor.

## 6. Primitives (`src/components/ui/`)

Built on Radix + cva + `cn` (from `@/lib/utils`, twMerge-backed). React 19 style (no forwardRef;
`data-slot` attributes).

| File | Replaces | Variants / notes |
|---|---|---|
| `button.tsx` | `.btn`, `.btn-accent`, `<a className="btn">` | `default`(amber) · `secondary` · `outline` · `ghost` · `destructive` · `link`; sizes `sm/default/lg/icon/icon-sm`. For `<a>` use `buttonVariants({...})`. Exports `buttonVariants`. |
| `badge.tsx` | `.chip` | `default · secondary · outline · success · warning · info · destructive` + **`score`** (pass `style={{ "--tone": fitTone(n) }}`). |
| `card.tsx` | `.card` | `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent`/`CardFooter`. |
| `input.tsx` `textarea.tsx` `label.tsx` | `<input className="btn">`, raw labels | themed fields + focus ring. |
| `select.tsx` | native `<select>` | Radix; content `z-[95]` (layers above sheets). **Item value can't be `""`** — map a sentinel (e.g. `"all"`). |
| `checkbox.tsx` `switch.tsx` | native checkboxes | Radix. |
| `dialog.tsx` | centered modals | overlay blur + animations. |
| `sheet.tsx` | the right-side drawer | Dialog anchored `side="right"` (DetailDrawer). |
| `tooltip.tsx` | `title=` attrs | wrap app in `TooltipProvider`. |
| `dropdown-menu.tsx` `tabs.tsx` `scroll-area.tsx` `separator.tsx` `skeleton.tsx` | — | standard. Tabs = the Pipeline/Portafolio toggle. |
| `command.tsx` | cmdk styling | used by CommandPalette. |
| `sonner.tsx` | inline flash messages | single `<Toaster theme={theme} />` mounted in `App`. |
| `kbd.tsx` | bare shortcut text | the ⌘K hint. |
| `score-ring.tsx` | flat score chip | conic ring colored by `fitTone()`; pass `centerClassName` to match the surface (`bg-card` on board, `bg-background` in the sheet). |
| `icons.ts` | **all emoji** | single icon source of truth (lucide). |

### Iconography
**No raw emoji in the UI.** Add icons to `src/components/ui/icons.ts` and import from there
(`actionIcon(type)`, `MatchIcon`, `KnockoutIcon`, `ReferralIcon`, `SalaryIcon`, `InsightsIcon`,
`CelebrateIcon`, `DowntimeIcon`). Everything else uses `lucide-react` directly.

## 7. Patterns

- **Dialog vs Sheet:** centered transient content → `Dialog`; side panel / record detail → `Sheet`.
- **Radix Select inside a Sheet/Dialog:** works because Select content is `z-[95]` (> sheet `z-50`)
  and portaled. Keep `position="popper"`.
- **Toasts:** `import { toast } from "sonner"` for confirmations (Copiado / Guardado / Enviado).
  The single `<Toaster>` lives in `App.tsx` and receives the theme.
- **Glass:** use `backdrop-blur` + `--highlight-top` only on floating surfaces, never on board cards
  (keeps dnd-kit drag math correct).

## 8. Invariants (must hold on every change)

1. **Visual only** unless the task is explicitly about logic — don't touch handlers, API calls
   (`src/api.ts`), props, state, or data flow.
2. **Keep Spanish user-facing strings.** Tests pin some (`NeedsAction`: `Todo al día`,
   `Acciones para hoy`, and clicking a card's title fires `onOpen`).
3. **Lint is `--max-warnings 0`.** `src/components/ui/**` has a scoped eslint override; everywhere
   else, sweep unused imports.
4. **`cn` comes from `@/lib/utils`** (twMerge). Domain helpers + `cn` re-export live in `@/lib`.
5. **No `*/` inside CSS comments** in `index.css` (e.g. `bg-*/text-*`) — it closes the comment early.

## 9. Verify

```bash
npm --prefix dashboard/frontend run lint          # eslint --max-warnings 0
npm --prefix dashboard/frontend run format:check   # prettier (run `format` to fix)
npm --prefix dashboard/frontend run typecheck      # tsc --noEmit
npm --prefix dashboard/frontend test               # vitest
npm --prefix dashboard/frontend run build          # vite build (NOT in check.sh — run it)
./scripts/check.sh                                  # full repo gate
```

Visual QA: start backend (`uv run uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8787`)
+ `npm --prefix dashboard/frontend run dev`, then check the onboarding gate, board, detail sheet,
command palette, and settings in **both themes** (header Sun/Moon toggle).

## 10. Extending with shadcn

`components.json` is configured (new-york, Vite, `@/` aliases, lucide). The official shadcn skill
auto-activates here. You can `npx shadcn@latest add <component>` — but **re-theme the generated file
to the tokens above and revert any edits the CLI makes to `src/index.css`** (it must not overwrite
the bespoke token system). Prefer hand-authoring in the existing style.
