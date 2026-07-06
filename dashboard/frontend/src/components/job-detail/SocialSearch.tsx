import { Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type SocialMention } from "../../api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";
import { Separator } from "../ui/separator";
import { SectionTitle } from "./SectionTitle";

// P2-C: supervised social signal. Atlas queues a search + prepares queries; the human
// runs the LinkedIn/X lookup in their own Chrome and saves what they confirm. No auto-contact.
export function SocialSearch({ jobId }: { jobId: string }) {
  const [mentions, setMentions] = useState<SocialMention[]>([]);
  const [queries, setQueries] = useState<Record<string, string> | null>(null);
  const [form, setForm] = useState({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
  const refresh = () => api.socialMentions(jobId).then((r) => setMentions(r.mentions));
  useEffect(() => {
    refresh();
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps
  const g = (q: string) => `https://www.google.com/search?q=${encodeURIComponent(q)}`;
  async function start() {
    setQueries((await api.startSocialSearch(jobId)).queries);
  }
  async function save() {
    if (!form.recruiter_name && !form.source_url) return;
    await api.addSocialMention(jobId, { platform: "linkedin", ...form });
    setForm({ recruiter_name: "", recruiter_linkedin: "", source_url: "" });
    refresh();
    toast.success("Mención guardada");
  }
  return (
    <div>
      <SectionTitle>Señal social (LinkedIn / X)</SectionTitle>
      <Card className="space-y-2.5 p-3.5 text-sm">
        <div className="text-[0.78rem] text-muted-foreground">
          Búsqueda supervisada en tu navegador — Atlas no contacta a nadie por ti.
        </div>
        <Button variant="secondary" size="sm" onClick={start}>
          <Search className="size-3.5" /> Buscar reclutador
        </Button>
        {queries && (
          <div className="flex flex-col gap-1 text-xs">
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_recruiters)}
            >
              · LinkedIn — reclutadores ↗
            </a>
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.linkedin_posts)}
            >
              · LinkedIn — posts de la vacante ↗
            </a>
            <a
              className="text-primary hover:underline"
              target="_blank"
              rel="noreferrer"
              href={g(queries.x)}
            >
              · X / Twitter ↗
            </a>
          </div>
        )}
        {mentions.map((m) => (
          <div key={m.id}>
            <Separator className="mb-2" />
            <b>{m.recruiter_name || m.post_title || "Mención"}</b>{" "}
            {m.platform && <Badge variant="secondary">{m.platform}</Badge>}
            {m.recruiter_linkedin && (
              <a
                className="ml-2 text-xs text-primary hover:underline"
                target="_blank"
                rel="noreferrer"
                href={m.recruiter_linkedin}
              >
                LinkedIn ↗
              </a>
            )}
            {m.source_url && (
              <a
                className="ml-2 text-xs text-primary hover:underline"
                target="_blank"
                rel="noreferrer"
                href={m.source_url}
              >
                fuente ↗
              </a>
            )}
          </div>
        ))}
        <div className="flex flex-col gap-1.5 pt-1">
          <Input
            className="h-8 text-xs"
            placeholder="Nombre del reclutador"
            value={form.recruiter_name}
            onChange={(e) => setForm({ ...form, recruiter_name: e.target.value })}
          />
          <Input
            className="h-8 text-xs"
            placeholder="URL de LinkedIn del reclutador"
            value={form.recruiter_linkedin}
            onChange={(e) => setForm({ ...form, recruiter_linkedin: e.target.value })}
          />
          <div className="flex gap-2">
            <Input
              className="h-8 flex-1 text-xs"
              placeholder="URL fuente (post)"
              value={form.source_url}
              onChange={(e) => setForm({ ...form, source_url: e.target.value })}
            />
            <Button variant="secondary" size="sm" onClick={save}>
              <Plus className="size-3.5" /> Guardar
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
