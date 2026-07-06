# Atlas Design System v2

Spec visual vinculante del dashboard (`dashboard/frontend/`). **Todo cambio de UI la sigue.**
Se aplica en dos capas: tokens/primitivos canónicos en código (`src/index.css` +
`src/components/ui/*`) y el skill `.claude/skills/atlas-design-system/` que trae los cambios
de IA de vuelta aquí. La dirección estética, paleta y tipografía nacen de
`docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md` (mockups aprobados).

> **Regla de oro:** componer desde `src/components/ui/*` y los tokens semánticos.
> Nada de botones/inputs/badges a mano ni colores hex.

## 1. Filosofía

**Meridian** invierte la personalidad del anterior sistema v1 ("Warm Editorial"):

- **Neutral frío** (slate/ink con matiz azulado) en vez de charcoal cálido — sin aurora, fondo
  plano.
- **Un solo acento de marca confiado**: un azul-índigo ("signal blue"), no ámbar/terracota.
  El ámbar sobrevive solo como color **funcional** de warning (nunca como identidad).
- **Tipografía nueva por completo**: Space Grotesk (geométrica, con carácter) + JetBrains Mono
  — se abandona Geist/Geist Mono.
- **Radius más ajustado** (0.5rem vs. el look más suave típico de shadcn) — personalidad de
  "instrumento de precisión" en vez de "amigable/editorial".
- **Tema por defecto: dark** (`:root` sin decorar = dark; `data-theme="light"` = override) —
  encaja con "command center" de búsqueda de empleo, con paridad completa en light.

Metáfora: Atlas como panel de control de una operación — data-dense, confiable, sin ruido
decorativo. El ámbar/verde/rojo/cian son semáforos funcionales, no la marca.

Reemplaza al "Warm Editorial" v1 (charcoal cálido + ámbar/terracota): ese sistema está RETIRADO.

## 2. Arquitectura de la app (v2)

- **Router:** react-router v7 (modo librería, paquete `react-router`). Rutas:
  `/pipeline` (default) · `/jobs/:id` (detalle con tabs Resumen/CV/Mensajes/Entrevistas/Research)
  · `/analytics` · `/portfolio` · `/settings` · `/onboarding`. `/` y `*` redirigen a `/pipeline`.
- **Shell:** `src/components/AppShell.tsx` — sidebar (tokens `--sidebar*`) + header compacto +
  ⌘K (CommandPalette con grupo "Ir a"). Toaster/diálogos globales viven aquí, una sola vez.
- **Datos:** TanStack Query v5. Hooks por recurso en `src/hooks/` (keys centralizadas en
  `src/hooks/keys.ts`). Páginas NUNCA llaman `api.*` directo para leer, ni `useEffect`+`useState`
  para datos de servidor.
- **Estados:** `LoadingState` / `ErrorState` / `EmptyState` de `src/components/ui/states.tsx` en
  toda página. `toast.loading→success/error` con `id` para operaciones largas; acciones
  destructivas con `action: Deshacer`.

## 3. Theming — `[data-theme]`, nunca `.dark`

`data-theme="dark" | "light"` en `<html>`, aplicado pre-paint en `main.tsx` y gestionado por
`src/hooks/useTheme.ts`. Variant de Tailwind ya cableada en `index.css`:
`@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`
No introducir la clase `.dark` ni cambiar el mecanismo.

## 4. Tokens (`src/index.css`)

OKLCH en `:root` (dark, default) y `:root[data-theme="light"]`, expuestos vía `@theme inline`.
Usar utilities (`bg-card`, `text-muted-foreground`, `border-border`, `ring-ring`, `bg-sidebar`,
`bg-sidebar-active`, …) o `var(--token)` — nunca colores crudos.

| Token | Utility | Uso |
|---|---|---|
| `--background` / `--foreground` | `bg-background` / `text-foreground` | lienzo / texto |
| `--card` / `--card-foreground` | `bg-card` | cards, tarjetas del kanban |
| `--popover` / `--popover-foreground` | `bg-popover` | menús, diálogos, palette |
| `--primary` / `--primary-foreground` | `bg-primary` / `text-primary` | acento de marca, botón primario |
| `--accent2` | `var(--accent2)` | acento secundario (referidos, ask_referral) |
| `--secondary` / `--secondary-foreground` | `bg-secondary` | botones secundarios, hovers, chips |
| `--muted-foreground` | `text-muted-foreground` | captions, texto apagado |
| `--success/warning/info/destructive` (+`-foreground`) | `bg-*`/`text-*` | semánticos |
| `--border` / `--input` / `--ring` | `border-border` / `border-input` / `ring-ring` | líneas, campos, foco |
| `--sidebar`, `--sidebar-foreground`, `--sidebar-border`, `--sidebar-active`, `--sidebar-active-foreground` | `bg-sidebar` etc. | app shell |
| `--chart-1..5` | `bg-chart-N` | embudo y charts |
| `--shadow-xs/sm/md/lg`, `--highlight-top` | `shadow-[var(--…)]` | elevación |
| `--radius` (+ sm/md/lg/xl) | `rounded-*` | radios |
| `--ease-out/in-out`, `--dur-fast/base/slow` | `ease-[var(--…)]` | motion |

### ⚠️ Reglas de nombres
- `accent`, `accent-foreground` y la superficie `muted` NO están mapeadas: **nunca**
  `bg-accent` / `text-accent-foreground` / `bg-muted`. Hover/superficies → `secondary`;
  texto apagado → `text-muted-foreground`.
- El compat layer `--color-*` de v1 **ya no existe**. `fitTone()` y `ACTION_META` (en `src/lib`)
  devuelven `var(--success|primary|info|warning|accent2|muted-foreground)`.
- No escribir `*/` dentro de comentarios CSS en `index.css`.

## 5. Tipografía y motion

Familias: `--font-sans` / `--font-mono` (paquetes @fontsource-variable importados en `main.tsx`;
Space Grotesk Variable y JetBrains Mono Variable, per visual-language doc). Escala: 
`text-display/h1/h2/h3/caption` (valores en `index.css`). `tabular-nums` SIEMPRE en números vivos 
(scores, métricas, %, salarios, contadores).
Motion: `--ease-*` + `--dur-*`, entradas con `.fade-up`, Radix vía `tw-animate-css`; respeta
`prefers-reduced-motion`. **Nunca** animar el transform de un nodo dnd-kit ni poner
`backdrop-filter`/`filter` en un ancestro draggable.

## 6. Primitivos (`src/components/ui/`)

Mismos 22 archivos y APIs que v1 (Button, Badge, Card, Checkbox, Command, Dialog, DropdownMenu,
icons, Input, Kbd, Label, ScoreRing, ScrollArea, Select, Separator, Sheet, Skeleton, Sonner,
Switch, Tabs, Textarea, Tooltip) + `states.tsx` (LoadingState/ErrorState/EmptyState).
Variants de Button: `default/secondary/outline/ghost/destructive/link`; sizes
`sm/default/lg/icon/icon-sm`. Variants de Badge: `default/secondary/outline/success/warning/
info/destructive/score` (score lee `--tone` por style, con `fitTone()`).
Iconos: SOLO lucide; los de dominio se declaran en `ui/icons.ts` (no emoji crudo en la UI).
Select: contenido `z-[95]`, `position="popper"`, item value nunca `""`.

## 7. Verificar

```bash
npm --prefix dashboard/frontend run lint          # eslint --max-warnings 0
npm --prefix dashboard/frontend run format:check
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
./scripts/check.sh
```

QA visual: backend (`uv run uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8787`) +
`npm --prefix dashboard/frontend run dev`; revisar /pipeline, /jobs/:id (5 tabs), /analytics,
/portfolio, /settings, /onboarding y la palette en **ambos temas**.

## 8. Extender con shadcn

`components.json` sigue configurado. Se puede `npx shadcn@latest add <componente>`, pero
re-tematizar el archivo generado a los tokens v2 y revertir cualquier edición que la CLI haga a
`src/index.css`. Preferir escribir a mano en el estilo existente.
