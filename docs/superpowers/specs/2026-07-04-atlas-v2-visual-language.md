# Atlas v2 — Visual Language: "Meridian"

**Fecha:** 2026-07-04 · **Autor:** Claude (carta blanca, aprobado por el usuario sin ronda de
mockups — ver decisión en la conversación: "Todo aprobado... procede a ejecutarlo todo").
**Consumido por:** [`plans/2026-07-04-atlas-v2-f1-ui-foundations.md`](../plans/2026-07-04-atlas-v2-f1-ui-foundations.md)
Task 1 (fuente única de verdad de los valores OKLCH/tipografía/sombras que ese plan marca
`/* ← visual-language doc */`).

## Dirección y por qué es distinta de "Warm Editorial"

Warm Editorial era charcoal cálido + ámbar/terracota como color de marca, Geist como única
fuente, superficie con una "aurora" de fondo. **Meridian** invierte esa personalidad:

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

## Tipografía

| Uso | Familia | Paquete Fontsource | Peso |
| --- | --- | --- | --- |
| `--font-sans` (todo: body, UI, headings) | `"Space Grotesk Variable"` | `@fontsource-variable/space-grotesk` | variable 300–700 |
| `--font-mono` (scores, ids, código) | `"JetBrains Mono Variable"` | `@fontsource-variable/jetbrains-mono` | variable 400–700 |

Instalar/desinstalar (Task 1, Step 2):
```bash
npm --prefix dashboard/frontend install @fontsource-variable/space-grotesk @fontsource-variable/jetbrains-mono
npm --prefix dashboard/frontend uninstall @fontsource-variable/geist @fontsource-variable/geist-mono
```

Imports en `main.tsx`:
```tsx
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
```

### Escala tipográfica (`@theme inline`)

| Token | Tamaño | Line-height | Letter-spacing | Weight |
| --- | --- | --- | --- | --- |
| `--text-caption` | `0.75rem` | `1.4` | `0.01em` | `500` |
| `--text-h3` | `0.9375rem` | `1.4` | — | `600` |
| `--text-h2` | `1.125rem` | `1.3` | `-0.01em` | `600` |
| `--text-h1` | `1.5rem` | `1.2` | `-0.015em` | `600` |
| `--text-display` | `2rem` | `1.15` | `-0.02em` | `600` |

## Radius

`--radius: 0.5rem` (8px) — único valor, compartido por ambos temas. Derivados en `@theme`:
`--radius-sm` (4px), `--radius-md` (6px), `--radius-lg` (8px), `--radius-xl` (12px).

## Canvas

Fondo del `body` es **plano**: `background: var(--background);` — sin gradiente ni aurora.

## Paleta — Dark (`:root`, tema por defecto)

| Token | Valor |
| --- | --- |
| `--background` | `oklch(0.17 0.014 258)` |
| `--foreground` | `oklch(0.95 0.004 258)` |
| `--card` | `oklch(0.21 0.015 258)` |
| `--card-foreground` | `oklch(0.95 0.004 258)` |
| `--popover` | `oklch(0.24 0.017 258)` |
| `--popover-foreground` | `oklch(0.95 0.004 258)` |
| `--primary` | `oklch(0.64 0.19 262)` |
| `--primary-foreground` | `oklch(0.99 0 0)` |
| `--accent2` | `oklch(0.72 0.14 200)` |
| `--secondary` | `oklch(0.27 0.016 258)` |
| `--secondary-foreground` | `oklch(0.93 0.006 258)` |
| `--muted-foreground` | `oklch(0.62 0.014 258)` |
| `--success` | `oklch(0.72 0.15 155)` |
| `--success-foreground` | `oklch(0.14 0.03 155)` |
| `--warning` | `oklch(0.78 0.15 80)` |
| `--warning-foreground` | `oklch(0.18 0.03 80)` |
| `--info` | `oklch(0.74 0.12 220)` |
| `--info-foreground` | `oklch(0.14 0.03 220)` |
| `--destructive` | `oklch(0.63 0.21 25)` |
| `--destructive-foreground` | `oklch(0.98 0.01 25)` |
| `--border` | `oklch(0.32 0.018 258)` |
| `--input` | `oklch(0.30 0.018 258)` |
| `--ring` | `oklch(0.64 0.19 262)` |
| `--sidebar` | `oklch(0.14 0.012 258)` |
| `--sidebar-foreground` | `oklch(0.88 0.008 258)` |
| `--sidebar-border` | `oklch(0.24 0.016 258)` |
| `--sidebar-active` | `oklch(0.27 0.06 262)` |
| `--sidebar-active-foreground` | `oklch(0.97 0.01 262)` |
| `--chart-1` | `oklch(0.64 0.19 262)` |
| `--chart-2` | `oklch(0.72 0.14 200)` |
| `--chart-3` | `oklch(0.72 0.15 155)` |
| `--chart-4` | `oklch(0.78 0.15 80)` |
| `--chart-5` | `oklch(0.68 0.18 320)` |
| `--shadow-xs` | `0 1px 2px oklch(0.05 0.01 258 / 0.30)` |
| `--shadow-sm` | `0 1px 3px oklch(0.05 0.01 258 / 0.35), 0 1px 2px oklch(0.05 0.01 258 / 0.25)` |
| `--shadow-md` | `0 4px 10px oklch(0.05 0.01 258 / 0.35), 0 2px 4px oklch(0.05 0.01 258 / 0.25)` |
| `--shadow-lg` | `0 12px 28px oklch(0.05 0.01 258 / 0.40), 0 4px 8px oklch(0.05 0.01 258 / 0.25)` |
| `--highlight-top` | `inset 0 1px 0 oklch(1 0 0 / 0.04)` |

## Paleta — Light (`:root[data-theme="light"]`)

| Token | Valor |
| --- | --- |
| `--background` | `oklch(0.985 0.003 258)` |
| `--foreground` | `oklch(0.22 0.014 258)` |
| `--card` | `oklch(1 0 0)` |
| `--card-foreground` | `oklch(0.22 0.014 258)` |
| `--popover` | `oklch(1 0 0)` |
| `--popover-foreground` | `oklch(0.22 0.014 258)` |
| `--primary` | `oklch(0.50 0.19 262)` |
| `--primary-foreground` | `oklch(0.99 0 0)` |
| `--accent2` | `oklch(0.52 0.13 200)` |
| `--secondary` | `oklch(0.94 0.006 258)` |
| `--secondary-foreground` | `oklch(0.28 0.014 258)` |
| `--muted-foreground` | `oklch(0.48 0.014 258)` |
| `--success` | `oklch(0.52 0.14 155)` |
| `--success-foreground` | `oklch(0.99 0.01 155)` |
| `--warning` | `oklch(0.60 0.16 80)` |
| `--warning-foreground` | `oklch(0.99 0.01 80)` |
| `--info` | `oklch(0.54 0.12 220)` |
| `--info-foreground` | `oklch(0.99 0.01 220)` |
| `--destructive` | `oklch(0.54 0.20 25)` |
| `--destructive-foreground` | `oklch(0.99 0.01 25)` |
| `--border` | `oklch(0.89 0.008 258)` |
| `--input` | `oklch(0.86 0.01 258)` |
| `--ring` | `oklch(0.50 0.19 262)` |
| `--sidebar` | `oklch(0.96 0.004 258)` |
| `--sidebar-foreground` | `oklch(0.30 0.014 258)` |
| `--sidebar-border` | `oklch(0.89 0.008 258)` |
| `--sidebar-active` | `oklch(0.90 0.05 262)` |
| `--sidebar-active-foreground` | `oklch(0.32 0.10 262)` |
| `--chart-1` | `oklch(0.50 0.19 262)` |
| `--chart-2` | `oklch(0.52 0.13 200)` |
| `--chart-3` | `oklch(0.52 0.14 155)` |
| `--chart-4` | `oklch(0.62 0.15 80)` |
| `--chart-5` | `oklch(0.54 0.18 320)` |
| `--shadow-xs` | `0 1px 2px oklch(0.2 0.02 258 / 0.06)` |
| `--shadow-sm` | `0 1px 3px oklch(0.2 0.02 258 / 0.08), 0 1px 2px oklch(0.2 0.02 258 / 0.05)` |
| `--shadow-md` | `0 4px 10px oklch(0.2 0.02 258 / 0.08), 0 2px 4px oklch(0.2 0.02 258 / 0.05)` |
| `--shadow-lg` | `0 12px 28px oklch(0.2 0.02 258 / 0.12), 0 4px 8px oklch(0.2 0.02 258 / 0.06)` |
| `--highlight-top` | `inset 0 1px 0 oklch(1 0 0 / 0.6)` |

## Notas de uso (para Tasks 2+ del plan F1, restyle de primitivos)

- `--primary` es el único acento de acción (botones primarios, focus ring, links, active nav).
- `--accent2` es un cian de apoyo — usar solo en charts/gradientes secundarios, nunca como
  color de botón primario (evita recrear un "segundo color de marca" competidor).
- `--warning` (ámbar) es exclusivamente funcional: knockouts, flags de restricción geo,
  reposts. Nunca decorativo ni de marca — es la única concesión de continuidad con v1, y es
  deliberada (ámbar = "atención" es una convención universal, no una herencia estética).
- `--chart-1..5` siguen el mismo orden de hue que `primary/accent2/success/warning/(violeta
  nuevo)` para que leyendas y badges compartan vocabulario de color.
