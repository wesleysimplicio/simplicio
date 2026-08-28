import { useEffect, useState } from "react";
import type { DesktopSnapshot } from "./contracts";
import { loadDesktopSnapshot } from "./bridge";
import { Shell, type View } from "./components/Shell";
import { AccessGate, LoadingScreen, SignInScreen } from "./screens/AccessScreens";
import { HomeScreen } from "./screens/HomeScreen";
import { ProvidersScreen } from "./screens/ProvidersScreen";
import { SecondaryScreen } from "./screens/SecondaryScreen";

function initialView(): View {
  if (typeof window === "undefined") return "home";
  const requested = new URLSearchParams(window.location.search).get("view");
  if (
    requested === "home" ||
    requested === "providers" ||
    requested === "activity" ||
    requested === "memory" ||
    requested === "settings"
  ) {
    return requested;
  }
  return "home";
}

export function DesktopApp({ snapshot: initialSnapshot }: { snapshot?: DesktopSnapshot }) {
  const [snapshot, setSnapshot] = useState<DesktopSnapshot | undefined>(initialSnapshot);
  const [loadFailed, setLoadFailed] = useState(false);
  const [view, setView] = useState<View>(initialView);

  useEffect(() => {
    if (initialSnapshot) return;
    let current = true;
    loadDesktopSnapshot()
      .then((next) => {
        if (current) setSnapshot(next);
      })
      .catch(() => {
        if (current) setLoadFailed(true);
      });
    return () => {
      current = false;
    };
  }, [initialSnapshot]);

  if (!snapshot && !loadFailed) return <LoadingScreen />;

  if (loadFailed) {
    return <AccessGate state="unknown" />;
  }

  if (!snapshot || snapshot.access.state === "signed_out") return <SignInScreen />;
  if (snapshot.access.state === "inactive" || snapshot.access.state === "unknown") {
    return <AccessGate state={snapshot.access.state} email={snapshot.access.email} />;
  }

  return (
    <Shell snapshot={snapshot} view={view} onViewChange={setView}>
      {view === "home" && <HomeScreen snapshot={snapshot} onProviders={() => setView("providers")} />}
      {view === "providers" && <ProvidersScreen snapshot={snapshot} />}
      {view !== "home" && view !== "providers" && <SecondaryScreen view={view} snapshot={snapshot} />}
    </Shell>
  );
}

export default function App() {
  return <DesktopApp />;
}
