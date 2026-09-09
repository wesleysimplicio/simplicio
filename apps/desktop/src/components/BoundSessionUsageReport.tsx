import type { BoundSessionUsage } from "../session_idle";
const metrics = [
  ["input_tokens", "Entrada"], ["output_tokens", "Saída"],
  ["reasoning_tokens", "Raciocínio"], ["cache_read_tokens", "Cache lido"],
  ["cache_write_tokens", "Cache escrito"],
] as const;

export function BoundSessionUsageReport({ usage }: { usage: BoundSessionUsage }) {
  return <section aria-label="Consumo por sessão" className="provider-usage-list">
    <h3>Consumo por sessão</h3>
    {usage.collection_partial && <p role="status">A coleta encontrou limites ou fontes indisponíveis. Os valores mostram a evidência preservada.</p>}
    {usage.session_reports.map(report => <div className="provider-usage-row" key={report.session_id}>
      <div className="provider-usage-row-heading"><strong>{report.session_id}</strong>
        <span className="neutral-badge">{report.status === "provider_session_not_bound" ? "Provider ainda não vinculado"
          : report.events === 0 ? "Aguardando consumo" : report.events + " eventos preservados"}</span></div>
      <dl>{metrics.map(([key, label]) => <div key={key}>
        <dt>{label}</dt><dd>{report.totals[key] === null ? "—" : report.totals[key].toLocaleString("pt-BR")}
          {report.totals[key] === null && report.known_totals[key] !== undefined
            && <small> · subtotal conhecido {report.known_totals[key]?.toLocaleString("pt-BR")}</small>}
        </dd>
      </div>)}</dl>
    </div>)}
    <p className="token-proof-note">Valores informados pelo provider e vinculados a esta sessão. Campos sem evidência permanecem —; novas informações podem chegar depois do fechamento.</p>
  </section>;
}
