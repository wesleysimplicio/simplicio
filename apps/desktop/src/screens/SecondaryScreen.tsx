import type { DesktopSnapshot } from "../contracts";
import type { View } from "../components/Shell";
import { Glyph } from "../components/Brand";

type LegacyView = Extract<View, "bot" | "activity" | "memory" | "settings">;

const copy: Record<LegacyView, { eyebrow: string; title: string; description: string }> = {
  bot: {
    eyebrow: "Agent Plane",
    title: "Bot Center",
    description: "Roster, sessões e Rooms são projetados pelo Runtime.",
  },
  activity: {
    eyebrow: "Recibos",
    title: "Atividade",
    description: "Execuções, cache e economia.",
  },
  memory: {
    eyebrow: "Local",
    title: "Memória",
    description: "Frescor, tamanho e origem.",
  },
  settings: {
    eyebrow: "Preferências",
    title: "Configurações",
    description: "Conta, atualização e diagnóstico.",
  },
};

export function SecondaryScreen({ view, snapshot }: { view: LegacyView; snapshot: DesktopSnapshot }) {
  const content = copy[view];
  return (
    <div className="page secondary-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">{content.eyebrow}</span>
          <h1>{content.title}</h1>
          <p>{content.description}</p>
        </div>
      </section>
      <section className="secondary-grid">
        <article className="panel secondary-hero">
          <div className="secondary-visual"><Glyph name={view === "memory" ? "memory" : view === "settings" ? "settings" : view === "bot" ? "spark" : "activity"} size={34} /></div>
          <span className="eyebrow">Em breve</span>
          <h2>Conectado ao mesmo Runtime</h2>
          <p>Dados compactos e versionados.</p>
        </article>
        <article className="panel secondary-facts">
          <h3>Estado atual</h3>
          <dl>
            <div><dt>Fonte</dt><dd>{snapshot.source}</dd></div>
            <div><dt>Runtime</dt><dd>{snapshot.runtime.state}</dd></div>
            <div><dt>Acesso</dt><dd>{snapshot.access.state}</dd></div>
          </dl>
          <button className="button button-secondary button-wide" type="button">Ver issue de implementação</button>
        </article>
      </section>
    </div>
  );
}
