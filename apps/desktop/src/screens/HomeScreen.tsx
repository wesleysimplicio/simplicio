import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";

const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });

export function HomeScreen({ snapshot, onProviders }: { snapshot: DesktopSnapshot; onProviders: () => void }) {
  const connected = snapshot.providers.filter((provider) => provider.state === "connected");

  return (
    <div className="page home-page">
      <section className="page-heading home-heading">
        <div>
          <span className="eyebrow">Olá, {snapshot.access.displayName ?? "você"}</span>
          <h1>Hoje você <em>economizou.</em></h1>
          <p>Runtime ativo · {connected.length} providers conectados</p>
        </div>
        <button className="button button-secondary" type="button">
          <Glyph name="refresh" size={17} /> Atualizar
        </button>
      </section>

      <section className="metrics-grid" aria-label="Resumo de economia">
        <article className="metric-card metric-primary">
          <div className="metric-topline">
            <span>Tokens poupados</span>
            <span className="verified-pill"><Glyph name="check" size={14} /> Verificado</span>
          </div>
          <div className="metric-value-row">
            <strong>{number.format(snapshot.savings.monthTokens / 1_000_000)}M</strong>
            <div className="metric-unit"><span>tokens</span><small>este mês</small></div>
          </div>
          <div className="metric-footer">
            <div className="metric-bar"><span style={{ width: `${snapshot.savings.monthPercent}%` }} /></div>
            <b>{number.format(snapshot.savings.monthPercent)}%</b>
            <span>menos contexto</span>
          </div>
          <div className="metric-corner">≈ {money.format(snapshot.savings.estimatedUsd)}</div>
        </article>

        <article className="metric-card compact-metric">
          <div className="metric-icon"><Glyph name="spark" /></div>
          <span>Cache hit</span>
          <strong>{number.format(snapshot.savings.cacheHitPercent)}%</strong>
          <p>contexto reutilizado</p>
          <small className="metric-trend">+8,1%</small>
        </article>

        <article className="metric-card compact-metric">
          <div className="metric-icon"><Glyph name="shield" /></div>
          <span>CPU-first</span>
          <strong>{snapshot.savings.deterministicRuns}</strong>
          <p>execuções</p>
          <small className="metric-trend">com recibo</small>
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
            <span className="healthy-badge"><span className="status-dot online" /> saudável</span>
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
            <div><dt>Último recibo</dt><dd>{snapshot.runtime.lastReceiptAt}</dd></div>
          </dl>
          <button className="button button-secondary button-wide" type="button">Abrir diagnóstico</button>
        </aside>
      </section>
    </div>
  );
}
