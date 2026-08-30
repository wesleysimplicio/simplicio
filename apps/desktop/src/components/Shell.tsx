import type { ReactNode } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Brand, Glyph, type GlyphName } from "./Brand";
import { t } from "../i18n";

export type View =
  | "today"
  | "chats"
  | "teams"
  | "automations"
  | "apps"
  | "home"
  | "bot"
  | "providers"
  | "activity"
  | "memory"
  | "settings";

const primaryNavigation: Array<{ id: View; label: string; icon: GlyphName }> = [
  { id: "today", label: t("nav.today"), icon: "home" },
  { id: "chats", label: t("nav.chats"), icon: "chat" },
  { id: "teams", label: t("nav.teams"), icon: "teams" },
  { id: "automations", label: t("nav.automations"), icon: "automation" },
  { id: "apps", label: t("nav.apps"), icon: "apps" },
];

const legacyLabels: Partial<Record<View, string>> = {
  home: t("nav.today"),
  bot: "Bot Center",
  providers: t("nav.providers"),
  activity: t("nav.activity"),
  memory: t("nav.memory"),
  settings: t("nav.settings"),
};

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
          <p className="nav-caption">ESPAÇO DE TRABALHO</p>
          {primaryNavigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => onViewChange(item.id)}
              type="button"
              aria-label={item.label}
              aria-current={view === item.id ? "page" : undefined}
            >
              <Glyph name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
          <p className="nav-caption nav-caption-spaced">CONTA</p>
          <button
            className={`nav-item ${view === "settings" ? "active" : ""}`}
            onClick={() => onViewChange("settings")}
            type="button"
            aria-label={t("nav.settings")}
            aria-current={view === "settings" ? "page" : undefined}
          >
            <Glyph name="settings" />
            <span>{t("nav.settings")}</span>
          </button>
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
          <button className="sidebar-account" type="button" onClick={() => onViewChange("settings")}>
            <span className="profile-button sidebar-avatar">{snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}</span>
            <span><strong>{snapshot.access.displayName ?? "Conta"}</strong><small>{snapshot.access.plan ?? "Plano não verificado"}</small></span>
          </button>
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
            <strong>{primaryNavigation.find((item) => item.id === view)?.label ?? legacyLabels[view]}</strong>
          </div>
          <div className="topbar-actions">
            <button className="space-switcher" type="button" disabled title="Space switcher aguardando o contrato Workspace do Runtime">
              <span className="space-dot" /> Pessoal <Glyph name="chevron" size={14} />
            </button>
            <button className="toolbar-button" type="button" disabled title="O launcher será habilitado quando o registro de capabilities estiver disponível"><Glyph name="plus" size={16} /> <span>Novo</span></button>
            <button className="toolbar-button toolbar-search" type="button" disabled title="OmniSearch aguardando o índice canônico do Runtime"><Glyph name="search" size={16} /> <span>Buscar</span><kbd>⌘K</kbd></button>
            <button className="toolbar-icon-button" type="button" disabled title="Live indisponível até o Runtime expor uma sessão ativa"><Glyph name="live" size={16} /></button>
            <button className="toolbar-icon-button" type="button" disabled title="Sem novas atenções"><Glyph name="attention" size={16} /></button>
            {snapshot.source === "preview" && <span className="preview-badge">Demonstração</span>}
            <span className="receipt-label">
              <span className="status-dot online" />
              Runtime ativo
            </span>
            <button
              className="profile-button"
              type="button"
              aria-label="Abrir configurações da conta"
              onClick={() => onViewChange("settings")}
            >
              {snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}
            </button>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
