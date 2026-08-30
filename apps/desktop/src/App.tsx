import { useEffect, useRef, useState } from "react";
import type { DesktopSnapshot } from "./contracts";
import type { BotActionRequest } from "./bot_center";
import { snapshotWithDemoBots } from "./bot_center";
import {
  beginDesktopLogin,
  loadDesktopSnapshot,
  logoutDesktop,
  openDesktopSubscription,
  refreshDesktopSnapshot,
  repairDesktopProviders,
  dispatchDesktopBotAction,
} from "./bridge";
import { Shell, type View } from "./components/Shell";
import { AccessGate, LoadingScreen, SignInScreen } from "./screens/AccessScreens";
import { HomeScreen } from "./screens/HomeScreen";
import { ProvidersScreen } from "./screens/ProvidersScreen";
import { MemoryScreen } from "./screens/MemoryScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { ActivityScreen } from "./screens/ActivityScreen";
import { BotCenterScreen } from "./screens/BotCenterScreen";
import { ProductSurfaceScreen } from "./screens/ProductScreens";
import { TokensScreen } from "./screens/TokensScreen";
import "./runtime_panels.css";

function initialView(): View {
  if (typeof window === "undefined") return "home";
  const requested = new URLSearchParams(window.location.search).get("view");
  if (
    requested === "today" ||
    requested === "chats" ||
    requested === "teams" ||
    requested === "automations" ||
    requested === "apps" ||
    requested === "home" ||
    requested === "bot" ||
    requested === "providers" ||
    requested === "tokens" ||
    requested === "activity" ||
    requested === "memory" ||
    requested === "settings"
  ) {
    return requested;
  }
  return "today";
}

export function DesktopApp({ snapshot: initialSnapshot }: { snapshot?: DesktopSnapshot }) {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | undefined>(initialSnapshot);
  const [botCenter, setBotCenter] = useState(initialSnapshot?.botCenter);
  const [loadFailed, setLoadFailed] = useState(false);
  const [action, setAction] = useState<"login" | "logout" | "refresh" | "repair" | "subscribe" | "bot" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [view, setView] = useState<View>(initialView);
  const actionLock = useRef(false);

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
      .catch(() => {
        if (current) setLoadFailed(true);
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
      setLoadFailed(false);
    } catch {
      setActionError("Não foi possível atualizar o Runtime.");
    } finally {
      setAction(null);
      actionLock.current = false;
    }
  }

  async function repairProviders(planDigest: string): Promise<boolean> {
    if (actionLock.current) return false;
    actionLock.current = true;
    setAction("repair");
    setActionError(null);
    try {
      const next = await repairDesktopProviders(planDigest);
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
      return true;
    } catch (error) {
      setActionError(String(error).includes("integration_plan_changed")
        ? "O plano mudou. Revise a configuração novamente antes de aplicar."
        : "O Runtime não confirmou a instalação completa. Pode haver alterações parciais; atualize o diagnóstico e revise um novo plano antes de tentar novamente.");
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
    try {
      const next = await beginDesktopLogin();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
      if (next.access.state === "active") setView("today");
    } catch {
      setActionError("O login não foi concluído.");
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
      setView("home");
    } catch {
      setActionError("Não foi possível sair com segurança.");
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
    return <AccessGate state="unknown" busy={action !== null} error={actionError} onRefresh={refresh} />;
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
        onSubscribe={subscribe}
      />
    );
  }

  return (
    <Shell snapshot={snapshot} view={view} onViewChange={setView}>
      {actionError && <div className="desktop-action-error" role="alert">{actionError}</div>}
      {view === "home" && (
        <HomeScreen
          snapshot={snapshot}
          busy={action === "refresh"}
          onProviders={() => setView("providers")}
          onActivity={() => setView("activity")}
          onDiagnostics={() => setView("settings")}
          onRefresh={refresh}
        />
      )}
      {(view === "today" || view === "chats" || view === "teams" || view === "automations" || view === "apps") && (
        <ProductSurfaceScreen view={view} snapshot={snapshot} botCenter={botCenter ?? snapshotWithDemoBots(snapshot)} />
      )}
      {view === "bot" && <BotCenterScreen snapshot={botCenter ?? snapshotWithDemoBots(snapshot)} onAction={botAction} />}
      {view === "providers" && (
        <ProvidersScreen
          snapshot={snapshot}
          busy={action !== null}
          repairing={action === "repair"}
          onRefresh={refresh}
          onRepair={repairProviders}
        />
      )}
      {view === "memory" && <MemoryScreen snapshot={snapshot} />}
      {view === "tokens" && <TokensScreen />}
      {view === "settings" && (
        <SettingsScreen snapshot={snapshot} busy={action !== null} onRefresh={refresh} onSubscribe={subscribe} onLogout={logout} logoutBusy={action === "logout"} />
      )}
      {view === "activity" && <ActivityScreen snapshot={snapshot} />}
    </Shell>
  );
}

export default function App() {
  return <DesktopApp />;
}
