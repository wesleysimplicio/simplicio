import { useMemo, useRef, useState } from "react";
import { exportDesktopSnapshot } from "../bridge";
import type { ActivityItem, DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";
import { createActivityProjection } from "../activity_projection";
import type { DesktopUsageState } from "../usage_store";

type StatusFilter = "all" | ActivityItem["status"];

export function redactedActivity(items: ActivityItem[], savingsProven = false) {
  return items.map(({ id, title, provider, savedTokens, occurredAt, status }) => ({
    id, title, provider, savedTokens: savingsProven ? savedTokens : null, occurredAt, status,
  }));
}

function downloadActivity(items: ActivityItem[], savingsProven: boolean) {
  if (typeof document === "undefined") return;
  const payload = JSON.stringify({ schema: "simplicio.activity-export/v1", items: redactedActivity(items, savingsProven) }, null, 2);
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

export function ActivityScreen({ snapshot, usage }: { snapshot: DesktopSnapshot; usage?: DesktopUsageState }) {
  const projection = createActivityProjection(snapshot);
  const savingsProven = snapshot.savings.proofKind === "measured" || snapshot.savings.proofKind === "replayed" || snapshot.savings.proofKind === "mixed";
  const [status, setStatus] = useState<StatusFilter>("all");
  const [provider, setProvider] = useState("all");
  const [page, setPage] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportLock = useRef(false);
  const pageSize = Math.max(1, Math.min(snapshot.limits.maxActivity, 5));
  const providers = useMemo(() => Array.from(new Set(projection.items.map((item) => item.provider))).sort(), [projection.items]);
  const filtered = projection.items.filter((item) => (status === "all" || item.status === status) && (provider === "all" || item.provider === provider));
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const shown = safePage === page ? visible : filtered.slice(safePage * pageSize, (safePage + 1) * pageSize);

  async function exportReceipts() {
    if (exportLock.current) return;
    exportLock.current = true; setExporting(true); setExported(null); setExportError(null);
    try {
      const path = await exportDesktopSnapshot("activity", { status, provider });
      if (path) setExported(path);
      else downloadActivity(filtered, savingsProven);
    } catch { setExportError("Não foi possível salvar os recibos em Downloads. Verifique as permissões e o espaço em disco."); }
    finally { exportLock.current = false; setExporting(false); }
  }

  return (
    <div className="page secondary-page">
      <section className="page-heading">
        <div>
          <span className="eyebrow">Recibos</span>
          <h1>Atividade</h1>
          <p>Execuções, cache e economia com evidência limitada ao snapshot.</p>\n          <p className="token-proof-note">Economia: <code>{snapshot.savings.proofKind}</code>{!savingsProven && " · indisponível neste recorte"}</p>
          <p className="token-proof-note">Changefeed da sessão: <code>{usage?.changefeed.connection ?? "offline"}</code> · {usage?.changefeed.projection ? "último snapshot do Runtime disponível" : "sem snapshot; economia não é inferida"}</p>
        </div>
        <button className="button button-secondary" type="button" disabled={exporting} onClick={() => void exportReceipts()}>{exporting ? "Exportando…" : "Exportar recibos"}</button>
      </section>
      {exported && <p className="export-feedback" role="status">Exportado para {exported}</p>}
      {exportError && <p className="inline-error" role="alert">{exportError}</p>}
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
              <div className={`activity-saving${savingsProven ? "" : " muted"}`}><strong>{savingsProven ? `−${item.savedTokens.toLocaleString("pt-BR")}` : "—"}</strong><span>{savingsProven ? "tokens" : "sem evidência"}</span></div>
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
