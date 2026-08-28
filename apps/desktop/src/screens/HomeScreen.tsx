import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";

const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });

export function HomeScreen({
  snapshot,
  busy,
  onProviders,
  onRefresh,
}: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  onProviders: () => void;
  onRefresh: () => void;
}) {
  const connected = snapshot.providers.filter((provider) => provider.state === "connected");
  const savingsAvailable = snapshot.savings.proofKind !== "unavailable";
  const savingsProof = snapshot.savings.proofKind === "measured"
    ? "Medido"
    : snapshot.savings.proofKind === "replayed"
      ? "Reproduzido"
      : snapshot.savings.proofKind === "unavailable"
        ? "Indisponível"
        : "Estimado";
  const monthPercent = Math.min(100, Math.max(0, snapshot.savings.monthPercent));
  const estimatedCost = snapshot.savings.estimatedUsd === null
    ? "—"
    : `≈ ${money.format(snapshot.savings.estimatedUsd)}`;
  const cacheHit = snapshot.savings.providerCache.hitPercent === null
    ? "—"
    : `${number.format(snapshot.savings.providerCache.hitPercent)}%`;

  return (
    <div className="page home-page">
      <section className="page-heading home-heading">
        <div>
          <span className="eyebrow">Olá, {snapshot.access.displayName ?? "você"}</span>
          <h1>Hoje você <em>economizou.</em></h1>
          <p>Runtime ativo · {connected.length} providers conectados</p>
        </div>
        <button className="button button-secondary" type="button" onClick={onRefresh} disabled={busy}>
          <Glyph name="refresh" size={17} /> {busy ? "Atualizando…" : "Atualizar"}
        </button>
      </section>

      <section className="metrics-grid" aria-label="Resumo de economia">
        <article className="metric-card metric-primary">
          <div className="metric-topline">
            <span>Tokens poupados</span>
            <span className="verified-pill"><Glyph name={savingsAvailable ? "check" : "refresh"} size={14} /> {savingsProof}</span>
          </div>
          <div className="metric-value-row">
            <strong>{savingsAvailable ? `${number.format(snapshot.savings.monthTokens / 1_000_000)}M` : "—"}</strong>
            <div className="metric-unit"><span>tokens</span><small>este mês</small></div>
          </div>
          <div className="metric-footer">
            <div className="metric-bar"><span style={{ width: `${monthPercent}%` }} /></div>
            <b>{savingsAvailable ? `${number.format(snapshot.savings.monthPercent)}%` : "—"}</b>
            <span>menos contexto</span>
          </div>
          <div className="metric-corner">{estimatedCost}</div>
        </article>

        <article className="metric-card compact-metric">
          <div className="metric-icon"><Glyph name="spark" /></div>
          <span>Cache da LLM</span>
          <strong>{cacheHit}</strong>
          <p>telemetria do provider</p>
          <small className="metric-trend">{snapshot.savings.providerCache.proofKind === "measured" ? "medido" : "sem telemetria"}</small>
        </article>

        <article className="metric-card compact-metric">
          <div className="metric-icon"><Glyph name="shield" /></div>
          <span>CPU-first</span>
          <strong>{snapshot.savings.decisionCache.proofKind === "measured" ? snapshot.savings.decisionCache.runs : "—"}</strong>
          <p>execuções</p>
          <small className="metric-trend">{snapshot.savings.decisionCache.proofKind === "measured" ? "com recibo" : "sem recibo"}</small>
        </article>

        <article className="metric-card compact-metric providers-metric">
          <div className="provider-stack" aria-hidden="true">
            {connected.slice(0, 4).map((provider) => <span key={provider.id}>{provider.name.slice(0, 1)}</span>)}
          </div>
          <span>Providers</span>
          <strong>{connected.length}</strong>
          <p>conectados</p>
          <button type="button" onClick={onProviders}>Ver todos <Glyph name="arrow" size={16} /></button>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Recente</span>
              <h2>Atividade</h2>
            </div>
            <button className="text-button" type="button">Ver relatório <Glyph name="arrow" size={16} /></button>
          </div>
          <div className="activity-list">
            {snapshot.activity.length === 0 && <div className="empty-state">Sem atividade verificada.</div>}
            {snapshot.activity.map((item) => (
              <div className="activity-row" key={item.id}>
                <span className={`activity-status ${item.status}`}>
                  <Glyph name={item.status === "attention" ? "refresh" : "check"} size={16} />
                </span>
                <div className="activity-copy">
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <span>{item.provider} · {item.occurredAt}</span>
                </div>
                <div className={`activity-saving ${item.savedTokens === 0 ? "muted" : ""}`}>
                  <strong>{item.savedTokens ? `−${number.format(item.savedTokens)}` : "—"}</strong>
                  <span>tokens</span>
                </div>
              </div>
            ))}
          </div>
        </article>

        <aside className="panel runtime-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Local</span>
              <h2>Runtime</h2>
            </div>
            <span className="healthy-badge"><span className={`status-dot ${snapshot.runtime.state === "healthy" ? "online" : "offline"}`} /> {snapshot.runtime.state}</span>
          </div>
          <div className="runtime-radar" aria-hidden="true">
            <span className="radar-ring ring-a" />
            <span className="radar-ring ring-b" />
            <span className="radar-ring ring-c" />
            <div className="radar-core"><Glyph name="spark" size={25} /></div>
          </div>
          <dl className="runtime-facts">
            <div><dt>Transporte</dt><dd>{snapshot.runtime.transport}</dd></div>
            <div><dt>Versão</dt><dd>v{snapshot.runtime.version}</dd></div>
            <div><dt>Último recibo</dt><dd>{snapshot.runtime.lastReceiptAt ?? "—"}</dd></div>
            <div><dt>Mapa local</dt><dd>{snapshot.savings.mapCache.status}</dd></div>
          </dl>
          <button className="button button-secondary button-wide" type="button">Abrir diagnóstico</button>
        </aside>
      </section>
    </div>
  );
}
