import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "indisponível";
  return `${Math.round(bytes / 1024)} KB`;
}

export function MemoryScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const map = snapshot.savings.mapCache;
  const fast = snapshot.runtime.optionalFast;
  return (
    <div className="page secondary-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">Local</span>
          <h1>Memória</h1>
          <p>Frescor, tamanho e origem do contexto determinístico.</p>
        </div>
      </section>
      <section className="memory-grid">
        <article className="panel memory-hero">
          <div className="secondary-visual"><Glyph name="memory" size={34} /></div>
          <span className="eyebrow">Mapa do repositório</span>
          <h2>{map.status === "ready" ? "Pronto para reutilizar" : "Aguardando recibo"}</h2>
          <p>Somente metadados bounded chegam ao Desktop; o conteúdo completo permanece no Runtime.</p>
        </article>
        <article className="panel memory-facts">
          <h3>Estado do cache</h3>
          <dl>
            <div><dt>Status</dt><dd>{map.status}</dd></div>
            <div><dt>Geração</dt><dd>{map.generation ?? "indisponível"}</dd></div>
            <div><dt>Tamanho</dt><dd>{formatBytes(map.bytes)}</dd></div>
            <div><dt>Digest</dt><dd>{map.digest ? `${map.digest.slice(0, 18)}…` : "indisponível"}</dd></div>
          </dl>
          <div className="memory-boundary">
            <span className="status-dot online" />
            <span>Entrega protegida por recibo</span>
          </div>
          <p className="memory-note">Fast opcional: {fast.required ? "requerido" : "não requerido"}; injeção em hooks: {fast.hookInjected ? "sim" : "não"}.</p>
        </article>
      </section>
    </div>
  );
}
