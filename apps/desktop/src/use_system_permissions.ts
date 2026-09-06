import { useCallback, useEffect, useRef, useState } from "react";
import { readPermissions, type PermissionRow, type PermissionStatus } from "./system_permissions";

export const permissionLabels: Record<PermissionStatus, string> = {
  unknown: "Não consultada", not_determined: "Ainda não solicitada",
  restricted: "Restrita pelo sistema", denied: "Negada",
  granted: "Concedida", not_granted: "Não concedida",
};

/** One observation policy for every permission-dependent screen; never requests access. */
export function useSystemPermissions() {
  const [rows, setRows] = useState<PermissionRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const native = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
  const generation = useRef(0);
  const active = useRef(false);
  const lock = useRef(false);
  const refresh = useCallback(async () => {
    if (!native || lock.current || !active.current) return;
    const current = generation.current;
    lock.current = true; setBusy(true);
    try {
      const next = await readPermissions();
      if (active.current && generation.current === current) { setRows(next); setError(""); }
    } catch {
      if (active.current && generation.current === current) {
        setRows([]); setError("Não foi possível consultar as permissões deste aplicativo.");
      }
    } finally {
      lock.current = false;
      if (active.current && generation.current === current) setBusy(false);
    }
  }, [native]);
  useEffect(() => {
    active.current = true; generation.current += 1; void refresh();
    const focus = () => { void refresh(); };
    window.addEventListener("focus", focus);
    // WKWebView does not reliably emit DOM focus on native app activation.
    const timer = window.setInterval(focus, 2000);
    return () => {
      active.current = false; generation.current += 1;
      window.clearInterval(timer); window.removeEventListener("focus", focus);
    };
  }, [refresh]);
  return { rows, setRows, busy, native, refresh, error };
}
