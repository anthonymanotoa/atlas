import {
  Brain,
  ClipboardCheck,
  Download,
  FileText,
  Globe,
  type LucideIcon,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";

type Feature = {
  icon: LucideIcon;
  title: string;
  what: string;
  behind: string;
  how: string;
};

const FEATURES: Feature[] = [
  {
    icon: ClipboardCheck,
    title: "Auditoría de CV",
    what: "Te da un score de tu CV maestro y recomendaciones concretas de qué editar.",
    behind:
      "Revisa tu master_cv.yaml contra buenas prácticas (logros cuantificados, el posicionamiento hacia tu rol objetivo, claridad, longitud, keywords) y clasifica los hallazgos en alta/media/baja con una sugerencia por cada uno. Determinista; mismo motor que `atlas advise`.",
    how: '📄 Botón "Auditoría de CV" (arriba a la derecha) → editás master_cv.yaml → "Re-evaluar" · CLI: atlas advise',
  },
  {
    icon: Search,
    title: "Buscar vacantes",
    what: "Trae vacantes nuevas de todas las fuentes y las puntúa contra tu CV.",
    behind:
      "Scrapers/APIs deterministas sobre las fuentes activas de tu perfil → dedupe → scoring por reglas (fit) + cobertura de keywords del CV (match) → preselecciona las que pasan el umbral. Sin IA: reproducible y gratis.",
    how: 'Botón "Buscar" (tarda ~1–2 min) · CLI: atlas discover && atlas score',
  },
  {
    icon: FileText,
    title: "Preparar (CV + mensajes)",
    what: "Adapta tu CV maestro a la oferta (ATS-safe) y redacta los borradores de outreach.",
    behind:
      "Reordena y selecciona SOLO lo que está en tu master_cv.yaml — nunca inventa — calcula cobertura de keywords y renderiza DOCX/PDF. Los mensajes (cover, cold email, recruiter, hiring manager, referido, nota) son plantillas rellenadas con tus datos. Determinista.",
    how: 'Abrí una tarjeta → "Generar borradores" / "CV PDF" · CLI: atlas prep <id>',
  },
  {
    icon: MessageSquare,
    title: "Entrevistas",
    what: "Agendás una ronda y genera un documento de preparación.",
    behind:
      "Cruza tu CV con las keywords del puesto: preguntas probables (conductuales + específicas del rol) por tipo de ronda, temas a repasar (gaps del JD) y tu evidencia STAR tomada de tus bullets reales. La investigación de cada entrevistador la hacés vos (te deja los enlaces).",
    how: "Detalle → Entrevistas → Agregar → Generar prep · CLI: atlas interview add/prep",
  },
  {
    icon: Globe,
    title: "Portafolio",
    what: "Genera un sitio web local con tu perfil. Nunca se publica.",
    behind:
      "Renderiza tu master_cv.yaml en un index.html independiente, en tu Mac. Podés guardar 'peers' (portafolios de referencia que investigás vos) para inspirarte.",
    how: "Pestaña Portafolio → Generar / Abrir · CLI: atlas portfolio generate",
  },
  {
    icon: Users,
    title: "Referidos",
    what: "Marca las vacantes donde tenés un contacto de 1er grado en esa empresa.",
    behind:
      "Importás tu Connections.csv de LinkedIn y Atlas lo cruza por empresa, en local. Prioriza esas vacantes (un referido convierte mucho más).",
    how: "CLI: atlas import-connections <csv> → atlas referrals",
  },
  {
    icon: TrendingUp,
    title: "Registrar resultado",
    what: "Anotás el resultado real (rechazado / respondió / entrevista / oferta).",
    behind:
      "Vos confirmás; Atlas guarda qué empresas convierten y cómo, para mejorar futuras decisiones. Nunca inventa un resultado.",
    how: "Detalle → Registrar resultado · CLI: atlas outcome <id>",
  },
  {
    icon: Download,
    title: "Exportar / Ajustes",
    what: "Exportás todo el pipeline a CSV con las columnas que elijas.",
    behind: "Lee la base de datos local y arma el CSV con tu plantilla de columnas.",
    how: "⚙️ Ajustes → elegí columnas → Descargar CSV · CLI: atlas export",
  },
];

function FeatureCard({ f }: { f: Feature }) {
  const Icon = f.icon;
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
          <Icon className="size-4" />
        </span>
        <div className="text-h3 font-semibold">{f.title}</div>
      </div>
      <p className="mt-2.5 text-sm">{f.what}</p>
      <p className="mt-1.5 text-[0.8rem] text-muted-foreground">
        <span className="font-medium text-foreground/80">Por detrás:</span> {f.behind}
      </p>
      <p className="mt-2 font-mono text-[0.72rem] text-muted-foreground">{f.how}</p>
    </Card>
  );
}

export function HelpGuide({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-[860px] gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-6 py-5">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-primary font-bold text-primary-foreground shadow-[var(--shadow-md)]">
              A
            </span>
            <div>
              <DialogTitle className="text-h1">Cómo funciona Atlas</DialogTitle>
              <DialogDescription>
                Tu copiloto local de búsqueda de empleo — privado, reproducible y a costo $0.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <ScrollArea className="max-h-[calc(88vh-92px)]">
          <div className="space-y-7 px-6 py-6">
            {/* Qué es */}
            <section>
              <p className="text-sm text-muted-foreground">
                Atlas descubre vacantes remotas, mide qué tan bien encajan con tu CV, te arma un CV
                adaptado por puesto, redacta los borradores de contacto, prepara tus entrevistas y
                genera tu portafolio. Vos revisás y enviás —{" "}
                <b className="text-foreground">Atlas nunca envía nada por su cuenta</b>.
              </p>
            </section>

            {/* Cómo funciona por detrás */}
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Zap className="size-4 text-primary" />
                <h3 className="text-h2">El flujo, por detrás</h3>
              </div>
              <Card className="p-4">
                <div className="flex flex-wrap items-center gap-2 text-[0.8rem]">
                  <Badge variant="secondary">Fuentes de empleo</Badge>
                  <span className="text-muted-foreground">→</span>
                  <Badge variant="secondary">Motor determinista (Python)</Badge>
                  <span className="text-muted-foreground">→</span>
                  <Badge variant="secondary">Base de datos local</Badge>
                  <span className="text-muted-foreground">→</span>
                  <Badge variant="secondary">Este dashboard</Badge>
                </div>
                <p className="mt-3 text-[0.8rem] text-muted-foreground">
                  Todo el procesamiento (buscar, puntuar, adaptar CV, redactar, prep, portafolio)
                  corre como <b className="text-foreground">Python determinista en tu Mac</b>: las
                  mismas entradas dan siempre el mismo resultado, sin costo y sin que tus datos
                  salgan de tu equipo.
                </p>
              </Card>
            </section>

            {/* ¿Dónde entra Claude? */}
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Brain className="size-4 text-primary" />
                <h3 className="text-h2">¿Dónde entra Claude (la IA)?</h3>
              </div>
              <Card className="border-[color-mix(in_oklch,var(--primary)_45%,var(--border))] bg-[color-mix(in_oklch,var(--primary)_7%,transparent)] p-4">
                <ul className="space-y-2.5 text-sm">
                  <li className="flex gap-2.5">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>
                      <b>El dashboard NO llama a Claude.</b> Buscar, puntuar, CV, mensajes, prep y
                      portafolio son determinismo puro. Por eso son instantáneos, gratis y privados.
                    </span>
                  </li>
                  <li className="flex gap-2.5">
                    <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>
                      <b>Claude entra en la orquestación y el criterio:</b> una tarea diaria (Claude
                      Cowork) corre <code className="font-mono">atlas brain</code> — Claude coordina
                      el pipeline y te escribe el “Resumen del día”. Y lo usás para asesoría
                      (cv-linkedin-advisor) y para mapear tu CV importado.
                    </span>
                  </li>
                  <li className="flex gap-2.5">
                    <Zap className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span>
                      <b>Costo $0:</b> corre sobre tu suscripción (Max), <b>sin API key</b> ni Agent
                      SDK. No hay cobro por uso.
                    </span>
                  </li>
                </ul>
              </Card>
            </section>

            <Separator />

            {/* Funcionalidades */}
            <section>
              <div className="mb-3 flex items-center gap-2">
                <h3 className="text-h2">Las funcionalidades</h3>
                <Badge variant="secondary">{FEATURES.length}</Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {FEATURES.map((f) => (
                  <FeatureCard key={f.title} f={f} />
                ))}
              </div>
            </section>

            {/* Primeros pasos */}
            <section>
              <div className="mb-3 flex items-center gap-2">
                <h3 className="text-h2">Primeros pasos</h3>
              </div>
              <ol className="space-y-2 text-sm">
                {[
                  "Dejá tu CV listo (import-cv o editá master_cv.yaml) y pulsá “Re-evaluar”.",
                  "Pulsá “Buscar” y revisá la columna “Preseleccionados”.",
                  "Abrí una tarjeta con buen match → “Generar borradores” y descargá el CV.",
                  "Agendá una entrevista y pulsá “Generar prep”.",
                  "Generá tu portafolio en la pestaña “Portafolio”.",
                ].map((step, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/15 text-[0.75rem] font-semibold text-primary tabular-nums">
                      {i + 1}
                    </span>
                    <span className="pt-0.5">{step}</span>
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
