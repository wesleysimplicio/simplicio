import { useMemo, useState } from "react";
import type { ActivityItem, DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";
import { createActivityProjection } from "../activity_projection";

type StatusFilter = "all" | ActivityItem["status"];

export function redactedActivity(items: ActivityItem[]) {
  return items.map(({ id, title, provider, savedTokens, occurredAt, status }) => ({
    id, title, provider, savedTokens, occurredAt, status,
  }));
}

function downloadActivity(items: ActivityItem[]) {
  if (typeof document === "undefined") return;
  const payload = JSON.stringify({ schema: "simplicio.activity-export/v1", items: redactedActivity(items) }, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "simplicio-activity.json";
  link.click();
  URL.revokeObjectURL(url);
}

function statusLabel(status: ActivityItem["status"]): string {
  return status === "verified" ? "verificado" : status === "running" ? "em execução" : "atenção";
}

export function ActivityScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const projection = createActivityProjection(snapshot);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [provider, setProvider] = useState("all");
  const [page, setPage] = useState(0);
  const pageSize = Math.max(1, Math.min(snapshot.limits.maxActivity, 5));
  const providers = useMemo(() => Array.from(new Set(projection.items.map((item) => item.provider))).sort(), [projection.items]);
  const filtered = projection.items.filter((item) => (status === "all" || item.status === status) && (provider === "all" || item.provider === provider));
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const shown = safePage === page ? visible : filtered.slice(safePage * pageSize, (safePage + 1) * pageSize);

  return (
    <div className="page secondary-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">Recibos</span>
          <h1>Atividade</h1>
          <p>Execuções, cache e economia com evidência limitada ao snapshot.</p>
        </div>
        <button className="button button-secondary" type="button" onClick={() => downloadActivity(filtered)}>Exportar recibos</button>
      </section>
      <section className="panel activity-page-panel">
        <div className="activity-toolbar">
          <div className="segmented-control" aria-label="Filtrar por estado">
            {(["all", "verified", "running", "attention"] as const).map((item) => (
              <button key={item} className={status === item ? "active" : ""} type="button" onClick={() => { setStatus(item); setPage(0); }}>
                {item === "all" ? "Todos" : statusLabel(item)}
              </button>
            ))}
          </div>
          <label className="activity-provider-filter">Provider
            <select value={provider} onChange={(event) => { setProvider(event.target.value); setPage(0); }}>
              <option value="all">Todos</option>
              {providers.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
        <div className="activity-page-list">
          {shown.length === 0 ? <p className="empty-state">Nenhum recibo neste filtro.</p> : shown.map((item) => (
            <article className="activity-page-row" key={item.id}>
              <div className={`activity-status ${item.status === "attention" ? "attention" : ""}`}><Glyph name="activity" size={15} /></div>
              <div className="activity-copy"><strong>{item.title}</strong><p>{item.detail}</p><span>{item.provider} · {new Date(item.occurredAt).toLocaleString("pt-BR")}</span></div>
              <div className="activity-saving"><strong>−{item.savedTokens.toLocaleString("pt-BR")}</strong><span>tokens</span></div>
            </article>
          ))}
        </div>
        <footer className="activity-pagination">
          <span>{filtered.length} recibo(s) · máximo {projection.pageSize} · {projection.reasonCode}</span>
          <div><button className="text-button" type="button" disabled={safePage === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>Anterior</button><span>Página {safePage + 1} de {pageCount}</span><button className="text-button" type="button" disabled={safePage >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>Próxima</button></div>
        </footer>
      </section>
    </div>
  );
}
