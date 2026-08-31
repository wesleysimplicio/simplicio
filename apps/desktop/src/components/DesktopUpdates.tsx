import { useCallback, useEffect, useRef, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { checkDesktopUpdate, compareVersions, DESKTOP_RELEASES_URL, DESKTOP_UPDATE_EVENT, DesktopUpdateError, type DesktopUpdateErrorCode, type DesktopUpdateResult } from "../desktop_updates";
import { Glyph } from "./Brand";

type CheckState = DesktopUpdateResult | { state: "checking"; currentVersion: string | null } |
  { state: "error" | "offline"; currentVersion: string | null; code: DesktopUpdateErrorCode | "preview" | "native_unavailable" };

const OPEN_UNCERTAIN = "Não foi possível confirmar a abertura; confira o navegador. A tentativa anterior ainda pode concluir. Uma nova tentativa só será feita se você clicar novamente.";

const failureMessages: Record<DesktopUpdateErrorCode | "preview" | "native_unavailable", string> = {
  preview: "Esta é uma prévia no navegador. Abra o Simplicio instalado para consultar sua versão real e procurar atualizações.",
  native_unavailable: "Não foi possível consultar o aplicativo nativo. Nenhuma atualização foi instalada. Tente novamente ou reinicie o Simplicio.",
  offline: "Sem conexão de rede. Não foi possível confirmar se existe uma atualização; conecte-se e tente novamente.",
  timeout: "A consulta excedeu o tempo limite. A versão mais recente não foi confirmada; tente novamente em instantes.",
  canceled: "A consulta foi cancelada. Nenhum arquivo foi baixado ou alterado.",
  invalid_version: "O aplicativo não informou uma versão válida. Não é seguro afirmar que ele está atualizado.",
  unsupported_target: "Não foi possível identificar um sistema e uma arquitetura compatíveis. Consulte os instaladores na página oficial.",
  request_failed: "Não foi possível consultar o GitHub. A versão mais recente permanece não confirmada.",
  rate_limited: "O GitHub limitou temporariamente as consultas. Aguarde um pouco ou abra a página oficial de releases.",
  invalid_response: "A resposta da distribuição não pôde ser validada. Não é seguro afirmar que o aplicativo está atualizado.",
  no_compatible_release: "Não foi encontrado um instalador Desktop compatível em até 30 releases recentes. Uma release apenas do Runtime não confirma uma atualização do aplicativo.",
};

export function DesktopUpdates() {
  const native = isTauri();
  const dialog = useRef<HTMLDialogElement>(null);
  const activeCheck = useRef<AbortController | null>(null);
  const openLock = useRef(false);
  const openAttempt = useRef(0);
  const openTimer = useRef<number | undefined>(undefined);
  const [visible, setVisible] = useState(false);
  const [status, setStatus] = useState<CheckState>({ state: "checking", currentVersion: null });
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  const invalidateOpenAttempt = useCallback(() => {
    const pending = openLock.current;
    openAttempt.current += 1;
    window.clearTimeout(openTimer.current);
    openTimer.current = undefined;
    openLock.current = false;
    return pending;
  }, []);

  const startCheck = useCallback(async () => {
    setVisible(true);
    if (activeCheck.current) return;
    if (!native) {
      setStatus({ state: "error", currentVersion: null, code: "preview" });
      return;
    }
    const controller = new AbortController();
    activeCheck.current = controller;
    setStatus({ state: "checking", currentVersion: null });
    let installedVersion: string | null = null;
    let timedOut = false;
    let cancel: () => void = () => undefined;
    const canceled = new Promise<never>((_, reject) => {
      cancel = () => reject(new DesktopUpdateError(timedOut ? "timeout" : "canceled"));
      controller.signal.addEventListener("abort", cancel, { once: true });
    });
    // Also bound the native, read-only version/target lookup, not only the HTTP call.
    const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, 20_000);
    const check = async () => {
      const [version, target] = await Promise.all([getVersion(), invoke<unknown>("desktop_update_target")]);
      if (controller.signal.aborted) throw new DesktopUpdateError("canceled");
      compareVersions(version, version);
      installedVersion = version;
      if (activeCheck.current === controller) setStatus({ state: "checking", currentVersion: version });
      return checkDesktopUpdate({ currentVersion: version, target, signal: controller.signal, online: navigator.onLine });
    };
    try {
      const result = await Promise.race([check(), canceled]);
      if (activeCheck.current === controller) setStatus(result);
    } catch (error) {
      if (activeCheck.current !== controller) return;
      const code = timedOut ? "timeout" : error instanceof DesktopUpdateError ? error.code : "native_unavailable";
      setStatus({ state: code === "offline" ? "offline" : "error", currentVersion: installedVersion, code });
    } finally {
      window.clearTimeout(timer);
      controller.signal.removeEventListener("abort", cancel);
      if (activeCheck.current === controller) activeCheck.current = null;
    }
  }, [native]);

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    const request = () => { if (!disposed) void startCheck(); };
    // This read-only DOM event also serves a settings button and honest browser preview.
    window.addEventListener(DESKTOP_UPDATE_EVENT, request);
    if (native) {
      void listen(DESKTOP_UPDATE_EVENT, request, { target: "main" }).then((release) => {
        if (disposed) release(); else unlisten = release;
      }).catch(() => {
        if (!disposed) {
          setStatus({ state: "error", currentVersion: null, code: "native_unavailable" });
          setVisible(true);
        }
      });
    }
    return () => {
      disposed = true;
      window.removeEventListener(DESKTOP_UPDATE_EVENT, request);
      unlisten?.();
      const pending = activeCheck.current;
      activeCheck.current = null;
      pending?.abort();
      invalidateOpenAttempt();
    };
  }, [native, startCheck, invalidateOpenAttempt]);

  useEffect(() => {
    if (visible && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [visible]);

  function close() {
    const pending = activeCheck.current;
    activeCheck.current = null;
    pending?.abort();
    if (invalidateOpenAttempt()) setOpenError(OPEN_UNCERTAIN);
    setOpening(false);
    dialog.current?.close();
    setVisible(false);
  }

  async function openReleases() {
    if (openLock.current) return;
    const attempt = ++openAttempt.current;
    openLock.current = true;
    setOpening(true);
    setOpenError(null);
    const settle = (message: string | null) => {
      if (openAttempt.current !== attempt) return;
      invalidateOpenAttempt();
      setOpening(false);
      setOpenError(message);
    };
    // This bounds only UI confirmation. The OS opener is not canceled or retried.
    openTimer.current = window.setTimeout(() => settle(OPEN_UNCERTAIN), 8_000);
    try {
      if (native) await invoke("desktop_open_releases");
      else window.open(DESKTOP_RELEASES_URL, "_blank", "noopener,noreferrer");
    } catch {
      settle("Não foi possível confirmar a abertura da página oficial. Confira o navegador antes de tentar novamente.");
    } finally {
      settle(null);
    }
  }

  if (!visible) return null;
  const result = "release" in status ? status : null;
  const failed = status.state === "error" || status.state === "offline";
  const heading = status.state === "checking" ? "Procurando atualizações…" : status.state === "available" ? "Nova versão do Simplicio" :
    status.state === "up_to_date" ? "Simplicio está atualizado" : status.state === "newer_local" ? "Versão local mais recente" : "Atualização não confirmada";
  const description = status.state === "checking" ? "Consultando os instaladores Desktop publicados no repositório oficial. Você pode cancelar esta consulta a qualquer momento." :
    status.state === "available" ? `Simplicio ${status.release.version} está disponível para esta plataforma. Abra a release para consultar as instruções e baixar o instalador.` :
    status.state === "up_to_date" ? "Sua versão corresponde à mais recente com um instalador Desktop compatível nas releases consultadas." :
    status.state === "newer_local" ? `Este app é mais recente que o Desktop ${status.release.version} encontrado no repositório. Nenhum downgrade será feito.` :
    "code" in status ? failureMessages[status.code] : "Não foi possível confirmar a atualização.";

  return <dialog className="project-dialog desktop-updates-dialog" ref={dialog} aria-labelledby="desktop-updates-heading"
    aria-describedby="desktop-updates-description" data-update-state={status.state} onCancel={(event) => { event.preventDefault(); close(); }}>
    <div className="dialog-heading"><span className="project-emblem"><Glyph name={status.state === "checking" ? "refresh" : failed ? "attention" : "check"} size={24} /></span>
      <button className="icon-button" type="button" onClick={close} aria-label="Fechar atualizações"><Glyph name="close" size={18} /></button></div>
    <div role="status" aria-live="polite" aria-atomic="true">
      <h2 id="desktop-updates-heading">{heading}</h2>
      <p id="desktop-updates-description">{description}</p>
      {status.currentVersion && <p className="field-hint">Versão deste aplicativo: <strong>{status.currentVersion}</strong></p>}
    </div>
    {result && <p className="field-hint">Pacote publicado: <strong>{result.release.assetName}</strong><br />
      Plataforma: {result.target.platform} · {result.target.arch}. Consulta de até 30 releases recentes.</p>}
    <p className="field-hint">Esta consulta não baixa nem instala arquivos, não verifica assinaturas e não modifica o Runtime, plugins ou integrações.</p>
    {openError && <p className="inline-error" role="alert">{openError}</p>}
    <div className="dialog-actions">
      <button className="button button-secondary" type="button" onClick={close}>{status.state === "checking" ? "Cancelar consulta" : "Fechar"}</button>
      {status.state !== "checking" && <button className="button button-secondary" type="button" onClick={() => void startCheck()} disabled={!native}>Verificar novamente</button>}
      {status.state !== "checking" && <button className="button button-primary" type="button" onClick={() => void openReleases()} disabled={opening}>{opening ? "Abrindo…" : "Ver releases oficiais"}</button>}
    </div>
  </dialog>;
}
