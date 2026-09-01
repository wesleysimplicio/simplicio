import { useEffect, useRef, useState } from "react";
import type { DesktopSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { snapshotWithDemoBots } from "./bot_center";
import {
  beginDesktopLogin,
  loadDesktopSnapshot,
  loadDesktopInstallDiagnostic,
  logoutDesktop,
  openDesktopSubscription,
  refreshDesktopSnapshot,
  repairDesktopProviders,
  dispatchDesktopBotAction,
} from "./bridge";
import { Shell, type View } from "./components/Shell";
import { AccessGate, LoadingScreen, SignInScreen } from "./screens/AccessScreens";
import { WorkbenchHome } from "./screens/WorkbenchHome";
import { PreferencesScreen } from "./screens/PreferencesScreen";
import { SetupScreen } from "./screens/SetupScreen";
import { ProjectDialog } from "./components/ProjectDialog";
import { DesktopUpdates } from "./components/DesktopUpdates";
import { installFailureMessage, installFailureRecovery, type InstallFailureRecovery } from "./install_failures";
import { runtimeFailureMessage } from "./runtime_failures";
import { isView, loadWorkbench, MAX_PROJECTS, moveHistory, navigate, WORKBENCH_KEY, type LocalProject, type NavigationEntry, type NavigationState, type WorkbenchState } from "./workbench";
import { viewNavigationEntry } from "./settings_navigation";
import { ProvidersScreen } from "./screens/ProvidersScreen";
import { MemoryScreen } from "./screens/MemoryScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { ActivityScreen } from "./screens/ActivityScreen";
import { BotCenterScreen } from "./screens/BotCenterScreen";
import { ProductSurfaceScreen } from "./screens/ProductScreens";
import { TokensScreen } from "./screens/TokensScreen";
import { ReferenceSettingsScreen } from "./screens/ReferenceSettingsScreen";
import { isReferenceSettingsView } from "./reference_screens";
import "./runtime_panels.css";

function initialView(fallback: View): View {
  if (typeof window === "undefined") return "home";
  const requested = new URLSearchParams(window.location.search).get("view");
  return isView(requested) ? requested : fallback;
}

export function DesktopApp({ snapshot: initialSnapshot }: { snapshot?: DesktopSnapshot }) {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | undefined>(initialSnapshot);
  const [botCenter, setBotCenter] = useState(initialSnapshot?.botCenter);
  const [loadFailed, setLoadFailed] = useState(false);
  const [action, setAction] = useState<"login" | "logout" | "refresh" | "repair" | "subscribe" | "bot" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [applicationRecovery, setApplicationRecovery] = useState<InstallFailureRecovery | undefined>();
  const [workbench, setWorkbench] = useState(loadWorkbench);
  const [history, setHistory] = useState<NavigationState>(() => ({ entries: [{
    view: initialView(workbench.selectedProjectId ? "project" : "home"),
    projectId: workbench.selectedProjectId,
    tokenRepo: "",
  }], index: 0 }));
  const route = history.entries[history.index];
  const selectedProject = workbench.projects.find((project) => project.id === route.projectId);
  const view = route.view === "project" && !selectedProject ? "home" : route.view;
  const [showProjectDialog, setShowProjectDialog] = useState(false);
  const [storageError, setStorageError] = useState<string | null>(null);
  const tokenRepo = route.tokenRepo;
  const actionLock = useRef(false);

  function setView(next: View, restoreRoute?: NavigationEntry) {
    setHistory((current) => navigate(current, viewNavigationEntry(current.entries[current.index], next, restoreRoute)));
  }

  function moveNavigation(direction: -1 | 1) {
    const next = moveHistory(history, direction);
    setHistory(next);
    const projectId = next.entries[next.index].projectId;
    saveWorkbench({ ...workbench, selectedProjectId: workbench.projects.some((project) => project.id === projectId) ? projectId : null });
  }

  function saveWorkbench(next: WorkbenchState) {
    setWorkbench(next);
    try {
      window.localStorage.setItem(WORKBENCH_KEY, JSON.stringify({ ...next, selectedProjectId: next.preferences.rememberProject ? next.selectedProjectId : null }));
      setStorageError(null);
    } catch {
      setStorageError("Não foi possível salvar as preferências neste computador. As alterações permanecem nesta sessão; verifique o espaço em disco.");
    }
  }

  function openProject(project: LocalProject) {
    saveWorkbench({ ...workbench, selectedProjectId: project.id });
    setHistory((current) => navigate(current, { view: "project", projectId: project.id, tokenRepo: "" }));
  }

  function addProject(project: LocalProject) {
    const exists = workbench.projects.some((item) => item.id === project.id);
    if (!exists && workbench.projects.length >= MAX_PROJECTS) {
      setStorageError("A lista comporta até 32 projetos. Remova um atalho para adicionar outro; isso não exclui arquivos.");
      return;
    }
    saveWorkbench({ ...workbench, projects: exists ? workbench.projects : [...workbench.projects, project], selectedProjectId: project.id });
    setHistory((current) => navigate(current, { view: "project", projectId: project.id, tokenRepo: "" }));
  }

  function projectTokens(path = "") {
    setHistory((current) => navigate(current, { view: "tokens", projectId: current.entries[current.index].projectId, tokenRepo: path }));
  }

  useEffect(() => {
    if (initialSnapshot) return;
    let current = true;
    loadDesktopSnapshot()
      .then((next) => {
        if (current) {
          setSnapshot(next);
          setBotCenter(next.botCenter);
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setLoadFailed(true);
          setActionError(runtimeFailureMessage(error, "query"));
        }
      });
    return () => {
      current = false;
    };
  }, [initialSnapshot]);

  useEffect(() => {
    if (view !== "setup") return;
    let current = true;
    loadDesktopInstallDiagnostic()
      .then((diagnostic) => {
        if (!current || diagnostic.status === "clear") return;
        setActionError(installFailureMessage(diagnostic.error));
        setApplicationRecovery(installFailureRecovery(diagnostic.error));
      })
      .catch(() => {
        if (!current) return;
        setActionError("Não foi possível consultar o recibo persistente da instalação. Uma nova aplicação permanece bloqueada até o diagnóstico ser esclarecido.");
        setApplicationRecovery("reconcile");
      });
    return () => { current = false; };
  }, [view]);

  async function refresh() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("refresh");
    setActionError(null);
    try {
      const next = await refreshDesktopSnapshot();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
    } catch (error) {
      setActionError(runtimeFailureMessage(error, "query"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function repairProviders(planDigest: string): Promise<boolean> {
    if (actionLock.current || (applicationRecovery && applicationRecovery !== "review")) return false;
    actionLock.current = true;
    setAction("repair");
    setActionError(null);
    try {
      const next = await repairDesktopProviders(planDigest);
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
      setApplicationRecovery(undefined);
      return true;
    } catch (error) {
      setActionError(installFailureMessage(error));
      setApplicationRecovery(installFailureRecovery(error));
      return false;
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function login() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("login");
    setActionError(null);
    // Keep the intended next screen while access is gated. A later successful
    // account verification must resume first-login setup, not skip to the home.
    setView("setup");
    try {
      const next = await beginDesktopLogin();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
    } catch (error) {
      // The account action may have completed before its snapshot query failed.
      // Never reuse the pre-action signed-out or active state as current proof.
      setLoadFailed(true);
      setActionError(runtimeFailureMessage(error, "login"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function subscribe() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("subscribe");
    setActionError(null);
    try {
      await openDesktopSubscription();
    } catch {
      setActionError("Não foi possível abrir os planos.");
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function logout() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("logout");
    setActionError(null);
    try {
      const next = await logoutDesktop();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
      setView("home");
    } catch (error) {
      // Do not leave authenticated screens available from a stale snapshot when
      // logout's final state is unknown. Verification is a separate read-only action.
      setLoadFailed(true);
      setActionError(runtimeFailureMessage(error, "logout"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function botAction(request: BotActionRequest) {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("bot");
    setActionError(null);
    try {
      setBotCenter(await dispatchDesktopBotAction(request, botCenter ?? snapshotWithDemoBots(snapshot!)));
    } catch {
      setActionError("O Agent API não aceitou esta ação; nenhuma mudança local foi aplicada.");
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  if (!snapshot && !loadFailed) return <LoadingScreen />;

  if (loadFailed) {
    return <AccessGate state="unknown" busy={action !== null} error={actionError} onRefresh={refresh} onLogin={login} loginBusy={action === "login"} onLogout={logout} logoutBusy={action === "logout"} />;
  }

  if (!snapshot || snapshot.access.state === "signed_out") {
    return <SignInScreen busy={action === "login"} error={actionError} onLogin={login} />;
  }
  if (snapshot.access.state === "inactive" || snapshot.access.state === "unknown") {
    return (
      <AccessGate
        state={snapshot.access.state}
        email={snapshot.access.email}
        busy={action !== null}
        error={actionError}
        onRefresh={refresh}
        onLogin={login}
        loginBusy={action === "login"}
        onSubscribe={subscribe}
        onLogout={logout}
        logoutBusy={action === "logout"}
      />
    );
  }

  if (view === "setup") return <SetupScreen snapshot={snapshot} busy={action !== null} applicationError={actionError} applicationRecovery={applicationRecovery}
    onSnapshot={(next) => { setSnapshot(next); setBotCenter(next.botCenter); }} onApply={repairProviders}
    onVerificationFailure={() => setApplicationRecovery("refresh")}
    onFinish={() => setView("home")} onDiagnostics={() => { setView("diagnostics"); void refresh(); }} />;

  return (
    <Shell snapshot={snapshot} view={view} route={route} onViewChange={setView} workbench={{ ...workbench, selectedProjectId: selectedProject?.id ?? null }}
      onAddProject={() => setShowProjectDialog(true)} onProject={openProject}
      onBack={() => moveNavigation(-1)} onForward={() => moveNavigation(1)}
      canBack={history.index > 0} canForward={history.index < history.entries.length - 1}
      onRefresh={refresh} busy={action !== null}>
      {actionError && <div className="desktop-action-error" role="alert">{actionError}</div>}
      {storageError && <div className="desktop-action-error" role="alert">{storageError}</div>}
      {(view === "home" || view === "project") && <WorkbenchHome key={selectedProject?.id ?? "home"} snapshot={snapshot}
        project={view === "project" ? selectedProject : undefined} onAddProject={() => setShowProjectDialog(true)}
        onViewChange={setView} onTokens={projectTokens} onRemoveProject={() => {
          saveWorkbench({ ...workbench, projects: workbench.projects.filter((item) => item.id !== selectedProject?.id), selectedProjectId: null });
          setHistory((current) => navigate({ ...current, entries: current.entries.map((entry) => entry.projectId === selectedProject?.id
            ? { view: "home" as const, projectId: null, tokenRepo: "" } : entry) }, { view: "home", projectId: null, tokenRepo: "" }));
        }} />}
      {(view === "today" || view === "chats" || view === "teams" || view === "automations" || view === "apps") && (
        <ProductSurfaceScreen view={view} snapshot={snapshot} botCenter={botCenter ?? snapshotWithDemoBots(snapshot)} />
      )}
      {view === "bot" && <BotCenterScreen snapshot={botCenter ?? snapshotWithDemoBots(snapshot)} onAction={botAction} />}
      {(view === "providers" || view === "agents") && (
        <ProvidersScreen
          key={view}
          inventoryOnly={view === "agents"}
          snapshot={snapshot}
          busy={action !== null}
          repairing={action === "repair"}
          onRefresh={refresh}
          onRepair={repairProviders}
          applicationRecovery={applicationRecovery}
          onDiagnostics={() => { setView("diagnostics"); void refresh(); }}
        />
      )}
      {view === "memory" && <MemoryScreen snapshot={snapshot} />}
      {view === "tokens" && <TokensScreen key={tokenRepo} initialRepoPath={tokenRepo} projectPaths={workbench.projects.map(project => project.path)} />}
      {(view === "settings" || view === "diagnostics") && (
        <SettingsScreen section={view === "diagnostics" ? "diagnostics" : "account"} snapshot={snapshot} busy={action !== null} onRefresh={refresh} onSubscribe={subscribe} onLogout={logout} logoutBusy={action === "logout"} />
      )}
      {(view === "general" || view === "shortcuts" || view === "models") && <PreferencesScreen view={view} snapshot={snapshot} preferences={workbench.preferences} onPreferences={(preferences) => saveWorkbench({ ...workbench, preferences })} onProviders={() => setView("agents")} />}
      {view === "activity" && <ActivityScreen snapshot={snapshot} />}
      {isReferenceSettingsView(view) && <ReferenceSettingsScreen key={view} view={view} snapshot={snapshot} onNavigate={setView} onRefresh={refresh} busy={action !== null} />}
      {showProjectDialog && <ProjectDialog onClose={() => setShowProjectDialog(false)} onAdd={addProject} />}
    </Shell>
  );
}

export default function App() {
  return <><DesktopApp /><DesktopUpdates /></>;
}
