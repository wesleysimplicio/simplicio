import { useEffect, useState } from "react";
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
import { SecondaryScreen } from "./screens/SecondaryScreen";
import { MemoryScreen } from "./screens/MemoryScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { ActivityScreen } from "./screens/ActivityScreen";
import { BotCenterScreen } from "./screens/BotCenterScreen";
import { ProductSurfaceScreen } from "./screens/ProductScreens";

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
    }
  }

  async function repairProviders() {
    setAction("repair");
    setActionError(null);
    try {
      const next = await repairDesktopProviders();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
    } catch {
      setActionError("Não foi possível reparar as integrações com segurança.");
    } finally {
      setAction(null);
    }
  }

  async function login() {
    setAction("login");
    setActionError(null);
    try {
      const next = await beginDesktopLogin();
      setSnapshot(next);
      setBotCenter(next.botCenter);
      setLoadFailed(false);
    } catch {
      setActionError("O login não foi concluído.");
    } finally {
      setAction(null);
    }
  }

  async function subscribe() {
    setAction("subscribe");
    setActionError(null);
    try {
      await openDesktopSubscription();
    } catch {
      setActionError("Não foi possível abrir os planos.");
    } finally {
      setAction(null);
    }
  }

  async function logout() {
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
    }
  }

  async function botAction(request: BotActionRequest) {
    setAction("bot");
    setActionError(null);
    try {
      setBotCenter(await dispatchDesktopBotAction(request, botCenter ?? snapshotWithDemoBots(snapshot!)));
    } catch {
      setActionError("O Agent API não aceitou esta ação; nenhuma mudança local foi aplicada.");
    } finally {
      setAction(null);
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
          busy={action === "refresh" || action === "repair"}
          repairing={action === "repair"}
          onRefresh={refresh}
          onRepair={repairProviders}
        />
      )}
      {view === "memory" && <MemoryScreen snapshot={snapshot} />}
      {view === "settings" && (
        <SettingsScreen snapshot={snapshot} busy={action === "refresh"} onRefresh={refresh} onSubscribe={subscribe} onLogout={logout} logoutBusy={action === "logout"} />
      )}
      {view === "activity" && <ActivityScreen snapshot={snapshot} />}
      {(view === "bot" || view === "memory" || view === "settings" || view === "activity") && <SecondaryScreen view={view} snapshot={snapshot} />}
    </Shell>
  );
}

export default function App() {
  return <DesktopApp />;
}
