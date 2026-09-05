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

type NativeUpdateState = {
  id?: string;
  state?: string;
  received_bytes?: number;
  asset_bytes?: number;
  status?: string;
};

type UpdateAction = {
  stage: "idle" | "downloading" | "ready" | "installing" | "awaiting_health" | "completed" | "rollback" | "error";
  id?: string;
  receivedBytes?: number;
  error?: string;
};

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
  return (bytes / divisor).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " " + unit;
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

function asNativeState(value: unknown): NativeUpdateState | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  return value as NativeUpdateState;
}

function nativeFailureMessage(code: string): string {
  const messages: Record<string, string> = {
    update_identity_invalid: "A identidade do pacote mudou. A atualização foi interrompida por segurança.",
    update_manifest_changed: "A release mudou desde a consulta. Verifique novamente antes de baixar.",
    update_digest_unavailable: "A distribuição não publicou um SHA-256 verificável para este pacote.",
    update_asset_invalid: "O pacote publicado não atende ao alvo ou ao contrato de distribuição.",
    update_download_failed: "O download falhou. O arquivo parcial foi preservado para retomar com segurança.",
    update_download_incomplete: "O download não terminou com o tamanho publicado. Tente novamente.",
    update_checksum_mismatch: "A verificação SHA-256 falhou. O pacote não será instalado.",
    update_stage_failed: "Não foi possível preparar o pacote em armazenamento privado.",
    update_package_unsupported: "Este pacote não pode ser instalado automaticamente nesta plataforma.",
    update_install_failed: "Não foi possível trocar o aplicativo atual. Nenhum downgrade foi feito.",
    update_rollback_failed: "A recuperação do aplicativo anterior falhou; não tente abrir o pacote manualmente.",
    update_rollback_unavailable: "Não há uma cópia anterior segura disponível para rollback.",
    update_target_unavailable: "Não foi possível localizar o aplicativo instalado para reiniciar.",
    update_not_ready: "O pacote ainda não está pronto para instalação.",
    update_not_downloaded: "Nenhum pacote verificado está disponível para instalação.",
  };
  return messages[code] || "A atualização não pôde ser concluída com segurança (" + code + ").";
}

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
  const [action, setAction] = useState<UpdateAction>({ stage: "idle" });
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
      setAction({ stage: "idle" });
      return;
    }
    const controller = new AbortController();
    activeCheck.current = controller;
    setAction({ stage: "idle" });
    setStatus({ state: "checking", currentVersion: null, progress: { stage: "identity", receivedBytes: 0 } });
    let installedVersion: string | null = null;
    let timedOut = false;
    let cancel: () => void = () => undefined;
    const canceled = new Promise<never>((_, reject) => {
      cancel = () => reject(new DesktopUpdateError(timedOut ? "timeout" : "canceled"));
      controller.signal.addEventListener("abort", cancel, { once: true });
    });
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

  const refreshNativeState = useCallback(async () => {
    if (!native) return;
    try {
      const state = asNativeState(await invoke<unknown>("desktop_update_status"));
      if (!state || !state.state) return;
      const receivedBytes = typeof state.received_bytes === "number" ? state.received_bytes : 0;
      if (state.state === "downloading") {
        setAction((previous) => ({ ...previous, stage: "downloading", id: state.id, receivedBytes }));
      } else if (state.state === "ready") {
        setAction((previous) => ({ ...previous, stage: "ready", id: state.id, receivedBytes }));
      } else if (state.state === "awaiting_health" || state.state === "relaunch_pending") {
        setAction((previous) => ({ ...previous, stage: "awaiting_health", id: state.id, receivedBytes }));
      } else if (state.state === "completed") {
        setAction((previous) => ({ ...previous, stage: "completed", id: state.id, receivedBytes }));
      }
    } catch {
      // Status is advisory; a failed poll must not turn a successful download into an error.
    }
  }, [native]);

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    const request = () => { if (!disposed) void startCheck(); };
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

  useEffect(() => {
    if (!visible || !native) return;
    let disposed = false;
    const poll = () => {
      if (!disposed) void refreshNativeState();
    };
    poll();
    const interval = window.setInterval(poll, action.stage === "downloading" ? 750 : 3_000);
    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, [visible, native, action.stage, refreshNativeState]);

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

  async function downloadUpdate() {
    if (!native || status.state !== "available") return;
    setAction({ stage: "downloading", receivedBytes: 0 });
    try {
      const value = asNativeState(await invoke<unknown>("desktop_update_download", {
        version: status.release.version,
        tag: status.release.tag,
        assetName: status.release.assetName,
        assetBytes: status.release.assetBytes,
      }));
      if (!value || value.state !== "ready" || !value.id) throw new Error("update_download_incomplete");
      setAction({ stage: "ready", id: value.id, receivedBytes: value.received_bytes || status.release.assetBytes });
    } catch (error) {
      const code = error instanceof Error ? error.message : String(error);
      setAction({ stage: "error", error: nativeFailureMessage(code) });
    }
  }

  async function installUpdate() {
    if (!native || !action.id) return;
    setAction({ stage: "installing", id: action.id });
    try {
      const value = asNativeState(await invoke<unknown>("desktop_update_install", { updateId: action.id }));
      if (!value || (value.state !== "awaiting_health" && value.state !== "relaunch_pending")) {
        throw new Error("update_install_failed");
      }
      setAction({ stage: "awaiting_health", id: action.id });
    } catch (error) {
      const code = error instanceof Error ? error.message : String(error);
      setAction({ stage: "error", id: action.id, error: nativeFailureMessage(code) });
    }
  }

  async function rollbackUpdate() {
    setAction((previous) => ({ ...previous, stage: "rollback" }));
    try {
      const value = asNativeState(await invoke<unknown>("desktop_update_rollback"));
      if (!value || value.status !== "rolled_back") throw new Error("update_rollback_failed");
      setAction({ stage: "completed" });
    } catch (error) {
      const code = error instanceof Error ? error.message : String(error);
      setAction((previous) => ({ ...previous, stage: "error", error: nativeFailureMessage(code) }));
    }
  }

  if (!visible) return null;
  const result = "release" in status ? status : null;
  const checking = status.state === "checking" ? status : null;
  const available = status.state === "available";
  const progressBytes = action.receivedBytes && result ? action.receivedBytes : 0;
  const progressRatio = result && progressBytes > 0 ? Math.min(100, progressBytes / result.release.assetBytes * 100) : undefined;
  const heading = status.state === "checking" ? "Procurando atualizações…" : status.state === "available" ? "Nova versão do Simplicio" :
    status.state === "up_to_date" ? "Simplicio está atualizado" : status.state === "newer_local" ? "Versão local mais recente" :
    action.stage === "ready" ? "Atualização pronta para instalar" : action.stage === "awaiting_health" ? "Confirmando reinicialização" :
    action.stage === "completed" ? "Atualização concluída" : "Atualização não confirmada";
  const description = status.state === "checking" ? "Consulta a distribuição oficial e valida o pacote compatível." :
    status.state === "available" ? "Simplicio " + status.release.version + " está disponível para esta plataforma." :
    status.state === "up_to_date" ? "Sua versão corresponde à mais recente com um instalador Desktop compatível nas releases consultadas." :
    status.state === "newer_local" ? "Este app é mais recente que o Desktop " + status.release.version + " encontrado no repositório. Nenhum downgrade será feito." :
    action.error || (action.stage === "downloading" ? "Baixando e verificando o pacote em armazenamento privado…" :
    action.stage === "ready" ? "O pacote foi baixado e conferido por SHA-256. Está pronto para instalar." :
    action.stage === "awaiting_health" ? "O aplicativo será reiniciado e validará a versão antes de confirmar a troca." :
    action.stage === "completed" ? "A versão em execução foi confirmada, ou o aplicativo anterior foi restaurado." :
    "Não foi possível confirmar a atualização.");

  return <dialog className="project-dialog desktop-updates-dialog" ref={dialog} aria-labelledby="desktop-updates-heading"
    aria-describedby="desktop-updates-description" data-update-state={status.state} data-update-action={action.stage}
    onCancel={(event) => { event.preventDefault(); close(); }}>
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
      <p>{checking.progress.receivedBytes > 0 ? formatBytes(checking.progress.receivedBytes) + " de metadados recebidos. " : ""}O instalador ainda não está sendo baixado.</p>
    </div>}
    {(action.stage === "downloading" || action.stage === "installing" || action.stage === "rollback") && <div className="desktop-update-progress" data-update-stage={action.stage}>
      <div className="desktop-update-progress-label"><span role="status" aria-live="polite">{action.stage === "downloading" ? "Baixando e verificando instalador" : action.stage === "installing" ? "Instalando e preparando reinício" : "Restaurando versão anterior"}</span>
        <span>{progressBytes > 0 && result ? formatBytes(progressBytes) + " de " + formatBytes(result.release.assetBytes) : "Aguarde…"}</span></div>
      <progress aria-label="Progresso do download" value={progressRatio} max="100" />
      <p>O arquivo é armazenado em área privada e só é instalado após a verificação de tamanho e SHA-256.</p>
    </div>}
    {status.currentVersion && <p className="desktop-update-installed">Versão deste aplicativo: <strong>{status.currentVersion}</strong></p>}
    {result && available && <>
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
    {status.state === "available" && action.stage === "idle" && <div className="desktop-update-manual"><Glyph name="external" size={17} /><div><strong>Atualização verificada pela distribuição</strong>
      <p>Baixe a release oficial para preparar uma instalação segura. O login do Simplicio não é necessário.</p></div></div>}
    {action.stage === "ready" && <div className="desktop-update-manual"><Glyph name="check" size={17} /><div><strong>Pacote pronto</strong>
      <p>O tamanho publicado e o SHA-256 foram conferidos. Você pode instalar e reiniciar quando quiser.</p></div></div>}
    {action.stage === "awaiting_health" && <div className="desktop-update-manual"><Glyph name="refresh" size={17} /><div><strong>Reinício em validação</strong>
      <p>Se a nova versão não iniciar corretamente, use rollback para voltar à cópia anterior.</p></div></div>}
    {action.error && <p className="inline-error" role="alert">{action.error}</p>}
    {!checking && <p className="desktop-update-caption">A consulta e a instalação são anônimas. A troca só é confirmada após iniciar a versão esperada; falhas podem restaurar a versão anterior.</p>}
    </div>
    {openError && <p className="inline-error" role="alert">{openError}</p>}
    <div className="dialog-actions desktop-update-actions">
      <button className="button button-secondary" type="button" onClick={close}>{status.state === "checking" ? "Cancelar consulta" : "Fechar"}</button>
      {status.state !== "checking" && <button className="button button-secondary" type="button" onClick={() => void startCheck()} disabled={!native || action.stage === "downloading" || action.stage === "installing"}>Verificar novamente</button>}
      {available && action.stage === "idle" && <button className="button button-primary" type="button" onClick={() => void downloadUpdate()} disabled={!native}>Baixar e verificar</button>}
      {available && action.stage === "ready" && <button className="button button-primary" type="button" onClick={() => void installUpdate()}>Instalar e reiniciar</button>}
      {["awaiting_health", "error"].includes(action.stage) && <button className="button button-secondary" type="button" onClick={() => void rollbackUpdate()} disabled={!native || !action.id}>Rollback</button>}
      {status.state !== "checking" && <button className="button button-secondary" type="button" onClick={() => void openReleases()} disabled={opening}>{opening ? "Abrindo…" : "Ver releases oficiais"}</button>}
    </div>
  </dialog>;
}

