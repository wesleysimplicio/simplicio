import { useEffect, useRef, useState, type ReactNode } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Brand, Glyph, type GlyphName } from "./Brand";
import { isSettingsView, runtimeSummary, searchMatches, VIEW_LABELS, type LocalProject, type View, type WorkbenchState } from "../workbench";

export type { View } from "../workbench";

interface Destination { id: View; icon: GlyphName; group?: string }
const navigation: Destination[] = [
  { id: "home", icon: "home" }, { id: "activity", icon: "activity" },
  { id: "agents", icon: "teams" }, { id: "providers", icon: "providers" }, { id: "tokens", icon: "spark" },
];
const settings: Destination[] = [
  { id: "agents", icon: "teams", group: "CAPACIDADES" },
  { id: "providers", icon: "providers", group: "CAPACIDADES" },
  { id: "models", icon: "spark", group: "CAPACIDADES" },
  { id: "settings", icon: "shield", group: "CONFIGURAÇÃO" },
  { id: "setup", icon: "check", group: "CONFIGURAÇÃO" },
  { id: "diagnostics", icon: "monitor", group: "CONFIGURAÇÃO" },
  { id: "memory", icon: "memory", group: "CONFIGURAÇÃO" },
  { id: "general", icon: "settings", group: "INTERFACE" },
  { id: "shortcuts", icon: "keyboard", group: "INTERFACE" },
];

interface ShellProps {
  children: ReactNode;
  snapshot: DesktopSnapshot;
  view: View;
  onViewChange: (view: View) => void;
  workbench: WorkbenchState;
  onAddProject: () => void;
  onProject: (project: LocalProject) => void;
  onBack: () => void;
  onForward: () => void;
  canBack: boolean;
  canForward: boolean;
  onRefresh: () => void;
  busy: boolean;
}

export function Shell({ children, snapshot, view, onViewChange, workbench, onAddProject, onProject,
  onBack, onForward, canBack, canForward, onRefresh, busy }: ShellProps) {
  const [collapsed, setCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 760);
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  const lastWorkspace = useRef<View>("home");
  const inSettings = isSettingsView(view);
  const status = runtimeSummary(snapshot);
  const selected = workbench.projects.find((project) => project.id === workbench.selectedProjectId);
  const modifier = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

  useEffect(() => {
    setQuery("");
    if (!isSettingsView(view)) lastWorkspace.current = view;
  }, [view]);

  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing || document.querySelector("dialog[open]")) return;
      if ((event.metaKey || event.ctrlKey) && !event.altKey) {
        if (event.key.toLowerCase() === "k") {
          event.preventDefault();
          setCollapsed(false);
          requestAnimationFrame(() => search.current?.focus());
        } else if (event.key.toLowerCase() === "b") {
          event.preventDefault();
          setCollapsed((current) => !current);
        } else if (event.key === ",") {
          event.preventDefault();
          onViewChange("settings");
        }
      } else if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault(); if (canBack) onBack();
      } else if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault(); if (canForward) onForward();
      }
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [onViewChange, canBack, canForward, onBack, onForward]);

  const destinations = query && !inSettings
    ? [...navigation, ...settings.filter((item) => !navigation.some((existing) => existing.id === item.id))]
    : inSettings ? settings : navigation;
  const matches = destinations.filter((item) => searchMatches(VIEW_LABELS[item.id] + " " + (item.group ?? ""), query));
  const projects = workbench.projects.filter((project) => searchMatches(project.name + " " + project.path, query));

  return (
    <div className={"app-shell workbench" + (collapsed ? " sidebar-collapsed" : "")} data-density={workbench.preferences.density}>
      <aside className="sidebar" aria-label={inSettings ? "Configurações" : "Espaço de trabalho"}>
        <div className="sidebar-heading">
          {inSettings ? <button className="back-to-app" type="button" onClick={() => onViewChange(lastWorkspace.current)} aria-label="Voltar ao app"><Glyph name="back" size={18} />{!collapsed && <span>Voltar ao app</span>}</button>
            : <button className="brand-home" type="button" onClick={() => onViewChange("home")} aria-label="Início do Simplicio"><Brand compact={collapsed} /></button>}
        </div>
        {!collapsed && <div className="sidebar-search-wrap">
          <label className="sidebar-search"><Glyph name="search" size={17} />
            <input ref={search} type="search" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={120}
              aria-label={inSettings ? "Buscar configurações" : "Buscar projetos e páginas"}
              placeholder={inSettings ? "Buscar configurações" : "Buscar no Simplicio"} />
            {!query && <kbd>{modifier} K</kbd>}
          </label>
        </div>}
        <div className="sidebar-scroll">
          <nav className="primary-nav" aria-label={inSettings ? "Categorias de configurações" : "Navegação principal"}>
            {matches.map((item, index) => <div key={item.id}>
              {!collapsed && inSettings && item.group !== matches[index - 1]?.group && <p className="nav-caption">{item.group}</p>}
              <button className={"nav-item" + (view === item.id ? " active" : "")} type="button" aria-label={VIEW_LABELS[item.id]}
                title={collapsed ? VIEW_LABELS[item.id] : undefined} aria-current={view === item.id ? "page" : undefined} onClick={() => onViewChange(item.id)}>
                <Glyph name={item.icon} size={18} />{!collapsed && <span>{VIEW_LABELS[item.id]}</span>}
                {!collapsed && !inSettings && item.id === "agents" && <small className="nav-count">{status.installed}</small>}
              </button>
            </div>)}
          </nav>
          {!inSettings && <section className="sidebar-projects" aria-label="Projetos locais">
            <div className="projects-heading">{!collapsed && <h2>PROJETOS</h2>}<button className="icon-button" type="button" aria-label="Adicionar projeto à lista" title="Adicionar projeto" onClick={onAddProject}><Glyph name="plus" size={17} /></button></div>
            {projects.map((project) => <button type="button" key={project.id} className={"nav-item project-nav" + (view === "project" && selected?.id === project.id ? " active" : "")}
              aria-label={"Abrir projeto " + project.name} title={project.path} aria-current={view === "project" && selected?.id === project.id ? "page" : undefined} onClick={() => onProject(project)}>
              <Glyph name="folder" size={17} />{!collapsed && <span className="project-nav-copy"><span>{project.name}</span>{workbench.preferences.showProjectPaths && <small>{project.path}</small>}</span>}
            </button>)}
            {!collapsed && !query && !projects.length && <p className="sidebar-empty">Adicione uma pasta para começar.<br />Seus arquivos ficam no computador.</p>}
          </section>}
          {!collapsed && query && !matches.length && (inSettings || !projects.length) && <div className="sidebar-empty" role="status">Nenhum resultado.<button className="text-button" type="button" onClick={() => setQuery("")}>Limpar busca</button></div>}
        </div>
        <div className="sidebar-bottom">
          <button className="nav-item" type="button" aria-label="Configurações" title="Configurações" onClick={() => onViewChange("settings")}><Glyph name="settings" size={18} />{!collapsed && <span>Configurações</span>}</button>
          <button className="icon-button" type="button" aria-label="Ver atalhos" title="Atalhos" onClick={() => onViewChange("shortcuts")}><Glyph name="keyboard" size={18} /></button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="workbench-history">
            <button className="icon-button" type="button" aria-label={collapsed ? "Expandir barra lateral" : "Recolher barra lateral"} aria-expanded={!collapsed} onClick={() => setCollapsed((current) => !current)}><Glyph name="sidebar" size={18} /></button>
            <span className="toolbar-separator" />
            <button className="icon-button" type="button" aria-label="Voltar" title="Voltar · Alt ←" onClick={onBack} disabled={!canBack}><Glyph name="back" size={17} /></button>
            <button className="icon-button" type="button" aria-label="Avançar" title="Avançar · Alt →" onClick={onForward} disabled={!canForward}><Glyph name="arrow" size={17} /></button>
          </div>
          <div className="topbar-path"><span>{inSettings ? "Configurações" : "Simplicio"}</span><span aria-hidden="true">/</span><strong>{view === "project" && selected ? selected.name : VIEW_LABELS[view]}</strong></div>
          <div className="topbar-actions">
            <button className="icon-button" type="button" aria-label="Atualizar Runtime" title="Atualizar estado do Runtime" disabled={busy} onClick={onRefresh}><Glyph name="refresh" size={17} /></button>
            <button className="profile-button" type="button" aria-label="Abrir configurações da conta" title="Conta Simplicio" onClick={() => onViewChange("settings")}>{snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}</button>
          </div>
        </header>
        <main className={"main-content" + (inSettings ? " settings-content" : "")} id="workbench-content">{children}</main>
      </div>

      <footer className="workbench-status" aria-label="Estado do Simplicio">
        <button type="button" onClick={() => onViewChange("diagnostics")} title="Abrir diagnóstico do Runtime"><span className={"status-dot " + (status.healthy ? "online" : "offline")} />{status.label}<span className="status-version">v{snapshot.runtime.version || "—"}</span></button>
        {snapshot.source === "preview" && <span className="preview-badge">Demonstração</span>}
        <span className="status-spacer" />
        <button className="status-savings" type="button" onClick={() => onViewChange("tokens")}><Glyph name="spark" size={14} />{status.measuredSavings === null ? "Economia sem medição" : status.measuredSavings.toLocaleString("pt-BR") + " tokens poupados"}</button>
        <button type="button" onClick={() => onViewChange("providers")}><Glyph name="providers" size={14} />{status.connected} MCP ativos</button>
        <span className="status-host"><Glyph name="monitor" size={14} />Este computador</span>
      </footer>
    </div>
  );
}
