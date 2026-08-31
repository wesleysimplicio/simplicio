import { useCallback, useEffect, useRef, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { checkDesktopUpdate, compareVersions, DESKTOP_RELEASES_URL, DESKTOP_UPDATE_EVENT, DesktopUpdateError, type DesktopUpdateErrorCode, type DesktopUpdateProgress, type DesktopUpdateResult } from "../desktop_updates";
import { Glyph } from "./Brand";
import "../desktop_updates.css";

type CheckProgress = DesktopUpdateProgress | { stage: "identity"; receivedBytes: 0 };
type CheckState = DesktopUpdateResult | { state: "checking"; currentVersion: string | null; progress: CheckProgress } |
  { state: "error" | "offline"; currentVersion: string | null; code: DesktopUpdateErrorCode | "preview" | "native_unavailable" };

const OPEN_UNCERTAIN = "Não foi possível confirmar a abertura; confira o navegador. A tentativa anterior ainda pode concluir. Uma nova tentativa só será feita se você clicar novamente.";

const progressLabels: Record<CheckProgress["stage"], string> = {
  identity: "Identificando este aplicativo",
  requesting: "Consultando a distribuição oficial",
  receiving: "Recebendo metadados das releases",
  validating: "Validando versão e pacote Desktop",
};

function formatBytes(bytes: number): string {
  const unit = bytes >= 1024 ** 3 ? "GiB" : bytes >= 1024 ** 2 ? "MiB" : bytes >= 1024 ? "KiB" : "B";
  const divisor = unit === "GiB" ? 1024 ** 3 : unit === "MiB" ? 1024 ** 2 : unit === "KiB" ? 1024 : 1;
  return `${(bytes / divisor).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${unit}`;
}

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
  const closeButton = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const activeCheck = useRef<AbortController | null>(null);
  const openLock = useRef(false);
  const openAttempt = useRef(0);
  const openTimer = useRef<number | undefined>(undefined);
  const [visible, setVisible] = useState(false);
  const [status, setStatus] = useState<CheckState>({ state: "checking", currentVersion: null, progress: { stage: "identity", receivedBytes: 0 } });
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
    if (!dialog.current?.open && document.activeElement instanceof HTMLElement) returnFocus.current = document.activeElement;
    setVisible(true);
    if (activeCheck.current) return;
    if (!native) {
      setStatus({ state: "error", currentVersion: null, code: "preview" });
      return;
    }
    const controller = new AbortController();
    activeCheck.current = controller;
    setStatus({ state: "checking", currentVersion: null, progress: { stage: "identity", receivedBytes: 0 } });
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
      return checkDesktopUpdate({ currentVersion: version, target, signal: controller.signal, online: navigator.onLine,
        onProgress: (progress) => {
          if (activeCheck.current === controller && !controller.signal.aborted) setStatus({ state: "checking", currentVersion: version, progress });
        },
      });
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
    if (visible && dialog.current && !dialog.current.open) {
      dialog.current.showModal();
      closeButton.current?.focus();
    }
  }, [visible]);

  function close() {
    const pending = activeCheck.current;
    activeCheck.current = null;
    pending?.abort();
    if (invalidateOpenAttempt()) setOpenError(OPEN_UNCERTAIN);
    setOpening(false);
    dialog.current?.close();
    setVisible(false);
    if (returnFocus.current?.isConnected) returnFocus.current.focus();
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
  const checking = status.state === "checking" ? status : null;
  const heading = status.state === "checking" ? "Procurando atualizações…" : status.state === "available" ? "Nova versão do Simplicio" :
    status.state === "up_to_date" ? "Simplicio está atualizado" : status.state === "newer_local" ? "Versão local mais recente" : "Atualização não confirmada";
  const description = status.state === "checking" ? "Consulta somente de metadados do Desktop." :
    status.state === "available" ? `Simplicio ${status.release.version} está disponível para esta plataforma.` :
    status.state === "up_to_date" ? "Sua versão corresponde à mais recente com um instalador Desktop compatível nas releases consultadas." :
    status.state === "newer_local" ? `Este app é mais recente que o Desktop ${status.release.version} encontrado no repositório. Nenhum downgrade será feito.` :
    "code" in status ? failureMessages[status.code] : "Não foi possível confirmar a atualização.";

  return <dialog className="project-dialog desktop-updates-dialog" ref={dialog} aria-labelledby="desktop-updates-heading"
    aria-describedby="desktop-updates-description" data-update-state={status.state} onCancel={(event) => { event.preventDefault(); close(); }}>
    <div className="desktop-update-topline"><span>Simplicio · Atualizações</span>
      <button className="icon-button" ref={closeButton} type="button" onClick={close} aria-label="Fechar atualizações"><Glyph name="close" size={18} /></button></div>
    <div className="desktop-update-summary">
      <img className="desktop-update-icon" src="/icon.png" alt="" width="64" height="64" />
      <div role="status" aria-live="polite" aria-atomic="true">
        <h2 id="desktop-updates-heading">{heading}</h2>
        <p id="desktop-updates-description">{description}</p>
      </div>
    </div>
    <div className="desktop-update-content">
    {checking && <div className="desktop-update-progress" data-update-stage={checking.progress.stage}>
      <div className="desktop-update-progress-label"><span role="status" aria-live="polite">{progressLabels[checking.progress.stage]}</span>
        <span>Etapa {checking.progress.stage === "identity" ? 1 : checking.progress.stage === "validating" ? 3 : 2} de 3</span></div>
      <progress aria-label="Progresso da consulta de atualização" />
      <p>{checking.progress.receivedBytes > 0 ? `${formatBytes(checking.progress.receivedBytes)} de metadados recebidos. ` : ""}O instalador não está sendo baixado.</p>
    </div>}
    {status.currentVersion && <p className="desktop-update-installed">Versão deste aplicativo: <strong>{status.currentVersion}</strong></p>}
    {result && <>
      <div className="desktop-update-package">
        <div><span><Glyph name="monitor" size={14} />{result.target.platform === "macos" ? "macOS" : result.target.platform === "windows" ? "Windows" : "Linux"} · {result.target.arch}</span>
          <span>{formatBytes(result.release.assetBytes)}</span></div>
        <strong>{result.release.assetName}</strong>
        <p>Release {result.release.tag}{result.release.publishedAt && <> · publicada em <time dateTime={result.release.publishedAt}>{new Date(result.release.publishedAt).toLocaleDateString("pt-BR", { timeZone: "UTC" })}</time></>}</p>
      </div>
      {result.release.notes ? <details className="desktop-update-notes">
        <summary>Notas da publicação <Glyph name="chevron" size={16} /></summary>
        <p>Texto público da release no GitHub; pode incluir Runtime e Desktop. Links e HTML não são executados aqui.</p>
        <pre>{result.release.notes.text}</pre>
        {result.release.notes.truncated && <p>Trecho limitado. Consulte a publicação completa na página oficial.</p>}
      </details> : <p className="desktop-update-caption">Esta publicação não informou notas de versão.</p>}
    </>}
    {!checking && <div className="desktop-update-manual"><Glyph name="external" size={17} /><div><strong>Download e instalação manuais</strong>
      <p>“Ver releases oficiais” abre a listagem no navegador. Localize {result ? `a release ${result.release.tag} e o pacote acima` : "um instalador compatível"} para baixar e instalar seguindo as instruções da publicação.</p></div></div>}
    {!checking && <p className="desktop-update-caption">Consulta de até 30 releases recentes. Não baixa ou extrai instaladores, não verifica assinaturas e não altera o Runtime, plugins ou integrações.</p>}
    </div>
    {openError && <p className="inline-error" role="alert">{openError}</p>}
    <div className="dialog-actions desktop-update-actions">
      <button className="button button-secondary" type="button" onClick={close}>{status.state === "checking" ? "Cancelar consulta" : "Fechar"}</button>
      {status.state !== "checking" && <button className="button button-secondary" type="button" onClick={() => void startCheck()} disabled={!native}>Verificar novamente</button>}
      {status.state !== "checking" && <button className="button button-primary" type="button" onClick={() => void openReleases()} disabled={opening}>{opening ? "Abrindo…" : "Ver releases oficiais"}</button>}
    </div>
  </dialog>;
}
