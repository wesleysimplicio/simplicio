import type { ReactNode } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Brand, Glyph, type GlyphName } from "./Brand";

export type View = "home" | "providers" | "activity" | "memory" | "settings";

const navigation: Array<{ id: View; label: string; icon: GlyphName }> = [
  { id: "home", label: "Início", icon: "home" },
  { id: "providers", label: "Providers", icon: "providers" },
  { id: "activity", label: "Atividade", icon: "activity" },
  { id: "memory", label: "Memória", icon: "memory" },
  { id: "settings", label: "Configurações", icon: "settings" },
];

interface ShellProps {
  children: ReactNode;
  snapshot: DesktopSnapshot;
  view: View;
  onViewChange: (view: View) => void;
}

export function Shell({ children, snapshot, view, onViewChange }: ShellProps) {
  const isHealthy = snapshot.runtime.state === "healthy";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <nav className="primary-nav" aria-label="Navegação principal">
          <p className="nav-caption">VISÃO GERAL</p>
          {navigation.slice(0, 3).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => onViewChange(item.id)}
              type="button"
              aria-label={item.label}
            >
              <Glyph name={item.icon} />
              <span>{item.label}</span>
              {item.id === "providers" && (
                <span className="nav-count">
                  {snapshot.providers.filter((provider) => provider.state === "connected").length}
                </span>
              )}
            </button>
          ))}
          <p className="nav-caption nav-caption-spaced">SISTEMA</p>
          {navigation.slice(3).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => onViewChange(item.id)}
              type="button"
              aria-label={item.label}
            >
              <Glyph name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-runtime">
          <div className="runtime-row">
            <span className={`status-dot ${isHealthy ? "online" : "offline"}`} />
            <div>
              <strong>Runtime {isHealthy ? "online" : "indisponível"}</strong>
              <span>{snapshot.runtime.version ? `v${snapshot.runtime.version}` : "sem versão"}</span>
            </div>
          </div>
          <div className="runtime-meta">
            <span>{snapshot.runtime.transport}</span>
            <span>{snapshot.runtime.lastReceiptAt ?? "sem recibo"}</span>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="window-controls" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="topbar-path">
            <strong>{navigation.find((item) => item.id === view)?.label}</strong>
          </div>
          <div className="topbar-actions">
            {snapshot.source === "preview" && <span className="preview-badge">Demonstração</span>}
            <span className="receipt-label">
              <span className="status-dot online" />
              Runtime ativo
            </span>
            <button className="profile-button" type="button" aria-label="Abrir menu da conta">
              {snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}
            </button>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
