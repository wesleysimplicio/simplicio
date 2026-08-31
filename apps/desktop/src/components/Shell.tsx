import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { DesktopSnapshot } from "../contracts";
import { Brand, Glyph, type GlyphName } from "./Brand";
import { REFERENCE_SCREENS, type ReferenceSettingsView } from "../reference_screens";
import { isNavigationVisible, isSettingsView, runtimeSummary, searchMatches, VIEW_LABELS, type LocalProject, type NavigationEntry, type View, type WorkbenchState } from "../workbench";
import { rememberWorkspaceRoute } from "../settings_navigation";

export type { View } from "../workbench";

interface Destination { id: View; icon: GlyphName; group?: string; description?: string }
const navigation: Destination[] = [
  { id: "home", icon: "home" }, { id: "activity", icon: "activity" },
  { id: "automations", icon: "automation" },
  { id: "agents", icon: "teams" }, { id: "providers", icon: "providers" }, { id: "tokens", icon: "spark" },
];
const referenceIcons: Record<ReferenceSettingsView, GlyphName> = {
  "provider-accounts": "providers", orchestration: "teams", "computer-use": "monitor", voice: "live",
  integrations: "providers", mobile: "monitor", "general-settings": "settings", artifacts: "folder",
  "share-skills": "spark", git: "folder", "task-sources": "activity", terminal: "keyboard",
  "quick-commands": "automation", browser: "external", emulator: "monitor", floating: "apps",
  input: "keyboard", notifications: "attention", hosts: "monitor", servers: "providers",
  permissions: "shield", privacy: "lock", advanced: "settings", experimental: "spark", plugins: "apps",
};
const groupOrder: Record<string, number> = {
  CAPACIDADES: 0, CONFIGURAÇÃO: 1, FLUXOS: 2, INTERFACE: 3,
  "HOSTS REMOTOS": 4, "PRIVACIDADE E SEGURANÇA": 5, AVANÇADO: 6, EXPERIMENTAL: 7,
};
const settings: Destination[] = ([
  { id: "agents", icon: "teams", group: "CAPACIDADES" },
  { id: "models", icon: "spark", group: "CAPACIDADES" },
  { id: "providers", icon: "providers", group: "CONFIGURAÇÃO" },
  { id: "settings", icon: "shield", group: "CONFIGURAÇÃO" },
  { id: "setup", icon: "check", group: "CONFIGURAÇÃO" },
  { id: "memory", icon: "memory", group: "FLUXOS" },
  { id: "tokens", icon: "spark", group: "FLUXOS" },
  { id: "general", icon: "settings", group: "INTERFACE" },
  { id: "shortcuts", icon: "keyboard", group: "INTERFACE" },
  { id: "diagnostics", icon: "monitor", group: "AVANÇADO" },
  ...REFERENCE_SCREENS.map(({ id, group, description }) => ({ id, group, description, icon: referenceIcons[id] })),
] satisfies Destination[]).filter((item) => isNavigationVisible(item.id));
settings.sort((left, right) => (groupOrder[left.group ?? ""] ?? 100) - (groupOrder[right.group ?? ""] ?? 100));

interface ShellProps {
  children: ReactNode;
  snapshot: DesktopSnapshot;
  view: View;
  route: NavigationEntry;
  onViewChange: (view: View, restoreRoute?: NavigationEntry) => void;
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

export function Shell({ children, snapshot, view, route, onViewChange, workbench, onAddProject, onProject,
  onBack, onForward, canBack, canForward, onRefresh, busy }: ShellProps) {
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.innerWidth < 760);
  const [collapsed, setCollapsed] = useState(() => typeof window !== "undefined" && window.innerWidth < 760);
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const sidebarScroll = useRef<HTMLDivElement>(null);
  const sidebarToggle = useRef<HTMLButtonElement>(null);
  const mainContent = useRef<HTMLElement>(null);
  const lastWorkspace = useRef<NavigationEntry>({ view: "home", projectId: route.projectId, tokenRepo: "" });
  const drawerOpen = narrow && !collapsed;
  const inSettings = isSettingsView(view);
  const status = runtimeSummary(snapshot);
  const registrations = snapshot.providers.filter((provider) => provider.registrationState === "registered").length;
  const selected = workbench.projects.find((project) => project.id === workbench.selectedProjectId);
  const modifier = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

  const closeSidebar = useCallback((focus: "toggle" | "content" | null = "toggle") => {
    setCollapsed(true);
    setQuery("");
    if (focus) requestAnimationFrame(() => {
      if (!document.querySelector("dialog[open]")) {
        (focus === "toggle" ? sidebarToggle.current : mainContent.current)?.focus({ preventScroll: true });
      }
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    if (collapsed) setCollapsed(false);
    else closeSidebar(drawerOpen ? "toggle" : null);
  }, [collapsed, drawerOpen, closeSidebar]);

  const selectView = useCallback((next: View, restoreRoute?: NavigationEntry) => {
    if (drawerOpen) closeSidebar("content");
    onViewChange(next, restoreRoute);
  }, [drawerOpen, closeSidebar, onViewChange]);

  function addProject() {
    if (drawerOpen) closeSidebar(null);
    onAddProject();
  }

  function selectProject(project: LocalProject) {
    if (drawerOpen) closeSidebar("content");
    onProject(project);
  }

  useEffect(() => {
    const media = window.matchMedia("(max-width: 759px)");
    function resize() {
      setNarrow(media.matches);
      if (media.matches) closeSidebar(sidebar.current?.contains(document.activeElement) ? "toggle" : null);
    }
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, [closeSidebar]);

  useEffect(() => {
    if (!drawerOpen) return;
    const frame = requestAnimationFrame(() => search.current?.focus());
    function containFocus(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing || document.querySelector("dialog[open]")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeSidebar();
      } else if (event.key === "Tab") {
        const controls = Array.from(sidebar.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), a[href], [tabindex='0']") ?? [])
          .filter((element) => element.getClientRects().length > 0);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)
          || !sidebar.current?.contains(document.activeElement)) {
          event.preventDefault();
          (event.shiftKey ? last : first)?.focus();
        }
      }
    }
    document.addEventListener("keydown", containFocus);
    return () => { cancelAnimationFrame(frame); document.removeEventListener("keydown", containFocus); };
  }, [drawerOpen, closeSidebar]);

  useEffect(() => {
    setQuery("");
    lastWorkspace.current = rememberWorkspaceRoute(lastWorkspace.current, { ...route, view });
  }, [route, view]);

  useEffect(() => { sidebarScroll.current?.scrollTo({ top: 0 }); }, [query]);

  useEffect(() => {
    if (collapsed || query) return;
    const frame = requestAnimationFrame(() => {
      const scroller = sidebarScroll.current;
      const active = scroller?.querySelector<HTMLElement>('[aria-current="page"]');
      if (!scroller || !active) return;
      const bounds = scroller.getBoundingClientRect();
      const item = active.getBoundingClientRect();
      const offset = item.top < bounds.top ? item.top - bounds.top : item.bottom > bounds.bottom ? item.bottom - bounds.bottom : 0;
      // Keep this scroller independent of the document's keyboard starting point.
      if (offset) scroller.scrollBy({ top: offset });
    });
    return () => cancelAnimationFrame(frame);
  }, [view, collapsed, query]);

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
          toggleSidebar();
        } else if (event.key === ",") {
          event.preventDefault();
          selectView("settings");
        }
      } else if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault(); if (canBack) { if (drawerOpen) closeSidebar("content"); onBack(); }
      } else if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault(); if (canForward) { if (drawerOpen) closeSidebar("content"); onForward(); }
      }
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [selectView, toggleSidebar, drawerOpen, closeSidebar, canBack, canForward, onBack, onForward]);

  const destinations = query && !inSettings
    ? [...navigation, ...settings.filter((item) => !navigation.some((existing) => existing.id === item.id))]
    : inSettings ? settings : navigation;
  const matches = destinations.filter((item) => searchMatches(VIEW_LABELS[item.id] + " " + (item.group ?? "") + " " + (item.description ?? ""), query));
  const projects = workbench.projects.filter((project) => searchMatches(project.name + " " + project.path, query));

  return (
    <div className={"app-shell workbench" + (collapsed ? " sidebar-collapsed" : "") + (drawerOpen ? " sidebar-overlay" : "")} data-density={workbench.preferences.density}>
      <a className="workbench-skip" href="#workbench-content" inert={drawerOpen} onClick={(event) => { event.preventDefault(); mainContent.current?.focus(); }}>Ir para o conteúdo</a>
      {drawerOpen && <button className="sidebar-scrim" type="button" aria-label="Fechar navegação" tabIndex={-1} onClick={() => closeSidebar()} />}
      <aside ref={sidebar} id="workbench-sidebar" className="sidebar" role={drawerOpen ? "dialog" : undefined} aria-modal={drawerOpen ? true : undefined} aria-label={inSettings ? "Configurações" : "Espaço de trabalho"}>
        <div className="sidebar-heading">
          {inSettings ? <button className="back-to-app" type="button" onClick={() => selectView(lastWorkspace.current.view, lastWorkspace.current)} aria-label="Voltar ao app"><Glyph name="back" size={18} />{!collapsed && <span>Voltar ao app</span>}</button>
            : <button className="brand-home" type="button" onClick={() => selectView("home")} aria-label="Início do Simplicio"><Brand compact={collapsed} /></button>}
          {drawerOpen && <button className="icon-button sidebar-close" type="button" aria-label="Recolher barra lateral" onClick={() => closeSidebar()}><Glyph name="close" size={18} /></button>}
        </div>
        {!collapsed && <div className="sidebar-search-wrap">
          <label className="sidebar-search"><Glyph name="search" size={17} />
            <input ref={search} type="search" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={120}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  const first = sidebar.current?.querySelector<HTMLButtonElement>(".primary-nav .nav-item, .project-nav");
                  if (first) { event.preventDefault(); first.focus(); }
                } else if (event.key === "Escape" && !drawerOpen && query) { event.preventDefault(); setQuery(""); }
              }}
              aria-label={inSettings ? "Buscar configurações" : "Buscar projetos e páginas"}
              placeholder={inSettings ? "Buscar configurações" : "Buscar no Simplicio"} />
            {!query && <kbd>{modifier} K</kbd>}
          </label>
        </div>}
        <div ref={sidebarScroll} className="sidebar-scroll">
          <nav className="primary-nav" aria-label={inSettings ? "Categorias de configurações" : "Navegação principal"}>
            {matches.map((item, index) => <div key={item.id}>
              {!collapsed && inSettings && item.group !== matches[index - 1]?.group && <p className="nav-caption">{item.group}</p>}
              <button className={"nav-item" + (view === item.id ? " active" : "")} type="button" aria-label={VIEW_LABELS[item.id]}
                title={collapsed ? VIEW_LABELS[item.id] : undefined} aria-current={view === item.id ? "page" : undefined} onClick={() => selectView(item.id)}>
                <Glyph name={item.icon} size={18} />{!collapsed && <span>{VIEW_LABELS[item.id]}</span>}
                {!collapsed && !inSettings && item.id === "agents" && <small className="nav-count">{status.installed}</small>}
              </button>
            </div>)}
          </nav>
          {!inSettings && <section className="sidebar-projects" aria-label="Projetos locais">
            <div className="projects-heading">{!collapsed && <h2>PROJETOS</h2>}<button className="icon-button" type="button" aria-label="Adicionar projeto à lista" title="Adicionar projeto" onClick={addProject}><Glyph name="plus" size={17} /></button></div>
            {projects.map((project) => <button type="button" key={project.id} className={"nav-item project-nav" + (view === "project" && selected?.id === project.id ? " active" : "")}
              aria-label={"Abrir projeto " + project.name} title={project.path} aria-current={view === "project" && selected?.id === project.id ? "page" : undefined} onClick={() => selectProject(project)}>
              <Glyph name="folder" size={17} />{!collapsed && <span className="project-nav-copy"><span>{project.name}</span>{workbench.preferences.showProjectPaths && <small>{project.path}</small>}</span>}
            </button>)}
            {!collapsed && !query && !projects.length && <p className="sidebar-empty">Adicione uma pasta para começar.<br />Seus arquivos ficam no computador.</p>}
          </section>}
          {!collapsed && query && !matches.length && (inSettings || !projects.length) && <div className="sidebar-empty" role="status">Nenhum resultado.<button className="text-button" type="button" onClick={() => { setQuery(""); search.current?.focus(); }}>Limpar busca</button></div>}
        </div>
        <div className="sidebar-bottom">
          <button className="nav-item" type="button" aria-label="Configurações" title="Configurações" onClick={() => selectView("settings")}><Glyph name="settings" size={18} />{!collapsed && <span>Configurações</span>}</button>
          {isNavigationVisible("shortcuts") && <button className="icon-button" type="button" aria-label="Ver atalhos" title="Atalhos" onClick={() => selectView("shortcuts")}><Glyph name="keyboard" size={18} /></button>}
        </div>
      </aside>

      <div className="workspace" inert={drawerOpen}>
        <header className="topbar">
          <div className="workbench-history">
            <button ref={sidebarToggle} className="icon-button" type="button" aria-label={collapsed ? "Expandir barra lateral" : "Recolher barra lateral"} aria-expanded={!collapsed} aria-controls="workbench-sidebar" onClick={toggleSidebar}><Glyph name="sidebar" size={18} /></button>
            <span className="toolbar-separator" />
            <button className="icon-button" type="button" aria-label="Voltar" title="Voltar · Alt ←" onClick={onBack} disabled={!canBack}><Glyph name="back" size={17} /></button>
            <button className="icon-button" type="button" aria-label="Avançar" title="Avançar · Alt →" onClick={onForward} disabled={!canForward}><Glyph name="arrow" size={17} /></button>
          </div>
          <div className="topbar-path"><span>{inSettings ? "Configurações" : "Simplicio"}</span><span aria-hidden="true">/</span><strong>{view === "project" && selected ? selected.name : VIEW_LABELS[view]}</strong></div>
          <div className="topbar-actions">
            <button className="icon-button" type="button" aria-label="Atualizar Runtime" title="Atualizar estado do Runtime" disabled={busy} onClick={onRefresh}><Glyph name="refresh" size={17} /></button>
            <button className="profile-button" type="button" aria-label="Abrir configurações da conta" title="Conta Simplicio" onClick={() => selectView("settings")}>{snapshot.access.displayName?.slice(0, 1).toUpperCase() ?? "S"}</button>
          </div>
        </header>
        <main ref={mainContent} tabIndex={-1} className={"main-content" + (inSettings ? " settings-content" : "")} id="workbench-content">{children}</main>
      </div>

      <footer className="workbench-status" aria-label="Estado do Simplicio" inert={drawerOpen}>
        <button type="button" onClick={() => selectView("diagnostics")} title="Abrir diagnóstico do Runtime"><span className={"status-dot " + (status.healthy ? "online" : "offline")} />{status.label}<span className="status-version">v{snapshot.runtime.version || "—"}</span></button>
        {snapshot.source === "preview" && <span className="preview-badge">Demonstração</span>}
        <span className="status-spacer" />
        <button className="status-savings" type="button" onClick={() => selectView("tokens")}><Glyph name="spark" size={14} />{status.measuredSavings === null ? "Economia sem medição" : status.measuredSavings.toLocaleString("pt-BR") + " tokens poupados"}</button>
        <button type="button" onClick={() => selectView("providers")} title={`${registrations} registros detectados. A conexão exige registro e handshake atuais; a ausência de confirmação não prova que o cliente está desconectado.`}><Glyph name="providers" size={14} />{status.connected} MCP {status.connected === 1 ? "confirmado" : "confirmados"}<span className="status-registrations">· {registrations} {registrations === 1 ? "registro detectado" : "registros detectados"}</span></button>
        <span className="status-host"><Glyph name="monitor" size={14} />Este computador</span>
      </footer>
    </div>
  );
}
