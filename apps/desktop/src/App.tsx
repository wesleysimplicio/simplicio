import { useEffect, useRef, useState } from "react";
import type { DesktopSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { snapshotWithDemoBots } from "./bot_center";
import {
  beginDesktopLogin,
  installDesktopRuntime,
  loadDesktopSnapshot,
  logoutDesktop,
  openDesktopSubscription,
  refreshDesktopSnapshot,
  reconcileDesktopRuntimeInstall,
  loadDesktopRuntimeInstallStatus,
  applyDesktopHostPlugins,
  reconcileDesktopHostPlugins,
  dispatchDesktopBotAction,
} from "./bridge";
import { Shell, type View } from "./components/Shell";
import { AccessGate, LoadingScreen, RuntimeInstallScreen, SignInScreen, type RuntimeInstallPhase } from "./screens/AccessScreens";
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
import type { HostPluginOperationResult } from "./integration_setup";
import type { RuntimeInstallResult } from "./runtime_install";
import { runtimeIsValid } from "./setup_flow";

function initialView(fallback: View): View {
  if (typeof window === "undefined") return "home";
  const requested = new URLSearchParams(window.location.search).get("view");
  return isView(requested) ? requested : fallback;
}

export function DesktopApp({ snapshot: initialSnapshot }: { snapshot?: DesktopSnapshot }) {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | undefined>(initialSnapshot);
  const [hostPluginOutcome, setHostPluginOutcome] = useState<HostPluginOperationResult | undefined>();
  const [botCenter, setBotCenter] = useState(initialSnapshot?.botCenter);
  const [loadFailed, setLoadFailed] = useState(false);
  const [action, setAction] = useState<"install" | "login" | "logout" | "refresh" | "repair" | "reconcile" | "subscribe" | "bot" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [runtimeInstallPhase, setRuntimeInstallPhase] = useState<RuntimeInstallPhase>("idle");
  const [runtimeInstallReceipt, setRuntimeInstallReceipt] = useState<RuntimeInstallResult | undefined>();
  const [runtimeInstallRecovery, setRuntimeInstallRecovery] = useState(false);
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
    loadDesktopRuntimeInstallStatus()
      .then((status) => {
        if (!current) return null;
        if (status.status === "pending") {
          setRuntimeInstallRecovery(true);
          setLoadFailed(true);
          return null;
        }
        return loadDesktopSnapshot();
      })
      .then((next) => {
        if (!next) return;
        if (current) {
          setSnapshot(next);
          setBotCenter(next.botCenter);
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setLoadFailed(true);
          const code = typeof error === "string" ? error : error instanceof Error ? error.message : "";
          setRuntimeInstallRecovery(code === "runtime_install_reconciliation_required");
          setActionError(code === "runtime_install_required" ? null : runtimeFailureMessage(error, "query"));
        }
      });
    return () => {
      current = false;
    };
  }, [initialSnapshot]);

  async function refresh() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("refresh");
    setActionError(null);
    try {
      const next = await refreshDesktopSnapshot();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setHostPluginOutcome(undefined);
      setApplicationRecovery(undefined);
      setLoadFailed(false);
    } catch (error) {
      setActionError(runtimeFailureMessage(error, "query"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function installRuntime() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("install");
    setActionError(null);
    setRuntimeInstallRecovery(false);
    setRuntimeInstallReceipt(undefined);
    setRuntimeInstallPhase("installing");
    let receipt: RuntimeInstallResult | undefined;
    try {
      // One explicit native install followed by one fresh read. The frontend
      // never retries either effect and never invokes host-plugin operations.
      receipt = await installDesktopRuntime();
      setRuntimeInstallReceipt(receipt);
      setRuntimeInstallPhase("validating");
      const next = await refreshDesktopSnapshot();
      if (!runtimeIsValid(next)) throw new Error("runtime_install_snapshot_invalid");
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setHostPluginOutcome(undefined);
      setApplicationRecovery(undefined);
      setLoadFailed(false);
      setRuntimeInstallPhase("idle");
      setView("home");
    } catch (error) {
      if (receipt) setRuntimeInstallReceipt(receipt);
      setLoadFailed(true);
      setRuntimeInstallPhase("failed");
      const code = typeof error === "string" ? error : error instanceof Error ? error.message : "";
      setRuntimeInstallRecovery(code === "runtime_install_reconciliation_required");
      setActionError(runtimeFailureMessage(error, "install"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function reconcileRuntimeInstall() {
    if (actionLock.current) return;
    actionLock.current = true;
    setAction("install");
    setRuntimeInstallPhase("validating");
    setActionError(null);
    try {
      const result = await reconcileDesktopRuntimeInstall();
      if (result.current) {
        const next = await refreshDesktopSnapshot();
        if (!runtimeIsValid(next)) throw new Error("runtime_install_snapshot_invalid");
        setSnapshot(next);
        setBotCenter(next.botCenter);
        setRuntimeInstallRecovery(false);
        setRuntimeInstallPhase("idle");
        setLoadFailed(false);
        setView("home");
      } else {
        setRuntimeInstallRecovery(false);
        setRuntimeInstallPhase("failed");
        setActionError("O estado foi reconciliado, mas o Runtime ainda não está instalado.");
      }
    } catch (error) {
      setRuntimeInstallPhase("failed");
      setRuntimeInstallRecovery(true);
      setActionError(runtimeFailureMessage(error, "install"));
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  function acceptHostPluginResult(result: HostPluginOperationResult) {
    setHostPluginOutcome(result);
    setApplicationRecovery(["partial", "requires_reconcile"].includes(result.snapshot.state) ? "reconcile" : undefined);
    setLoadFailed(false);
  }

  async function repairProviders(planDigest: string): Promise<HostPluginOperationResult> {
    if (actionLock.current || (applicationRecovery && applicationRecovery !== "review")) throw new Error("host_plugin_operation_blocked");
    actionLock.current = true;
    setAction("repair");
    setActionError(null);
    try {
      const result = await applyDesktopHostPlugins(planDigest);
      acceptHostPluginResult(result);
      return result;
    } catch (error) {
      setActionError(installFailureMessage(error));
      setApplicationRecovery(installFailureRecovery(error));
      throw error;
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function reconcileProviders(receiptId: string): Promise<HostPluginOperationResult> {
    if (actionLock.current) throw new Error("host_plugin_operation_busy");
    actionLock.current = true;
    setAction("reconcile");
    setActionError(null);
    try {
      const result = await reconcileDesktopHostPlugins(receiptId);
      acceptHostPluginResult(result);
      return result;
    } catch (error) {
      setActionError(installFailureMessage(error));
      setApplicationRecovery("reconcile");
      throw error;
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
    // Account entry always targets the normal application. If the following
    // snapshot is ambiguous, this route remains hidden behind the access gate.
    setView("home");
    try {
      const next = await beginDesktopLogin();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setHostPluginOutcome(undefined);
      setApplicationRecovery(undefined);
      setLoadFailed(false);
      setView("home");
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
      setHostPluginOutcome(undefined);
      setApplicationRecovery(undefined);
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

  if ((!snapshot && loadFailed) || (snapshot && !runtimeIsValid(snapshot))) {
    return <RuntimeInstallScreen
      phase={runtimeInstallPhase}
      receipt={runtimeInstallReceipt}
      error={actionError}
      onInstall={installRuntime}
      reconciliationRequired={runtimeInstallRecovery}
      onReconcile={reconcileRuntimeInstall}
    />;
  }

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
    initialOutcome={hostPluginOutcome} onSnapshot={(next) => {
      setSnapshot(next); setBotCenter(next.botCenter); setHostPluginOutcome(undefined); setApplicationRecovery(undefined); setActionError(null);
    }} onApply={repairProviders}
    onReconcile={reconcileProviders}
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
          repairing={action === "repair" || action === "reconcile"}
          onRefresh={refresh}
          onRepair={repairProviders}
          onReconcile={reconcileProviders}
          hostPluginOutcome={hostPluginOutcome}
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
