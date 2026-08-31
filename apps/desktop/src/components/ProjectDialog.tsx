import { useEffect, useRef, useState } from "react";
import { chooseDesktopProject, validateDesktopProject } from "../bridge";
import { Glyph } from "./Brand";
import type { LocalProject } from "../workbench";

export function ProjectDialog({ onClose, onAdd }: { onClose: () => void; onAdd: (project: LocalProject) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pathInput = useRef<HTMLInputElement>(null);
  const chooseButton = useRef<HTMLButtonElement>(null);
  const lock = useRef(false);
  const mounted = useRef(false);
  const focusAfterOperation = useRef<"path" | "choose" | null>(null);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [chosen, setChosen] = useState(false);
  const [pathInvalid, setPathInvalid] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const element = dialog.current;
    const invoker = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    mounted.current = true;
    element?.showModal();
    chooseButton.current?.focus();
    return () => {
      mounted.current = false;
      element?.close();
      if (invoker?.isConnected) invoker.focus();
    };
  }, []);

  useEffect(() => {
    if (busy || !focusAfterOperation.current) return;
    (focusAfterOperation.current === "choose" ? chooseButton : pathInput).current?.focus();
    focusAfterOperation.current = null;
  }, [busy]);

  function failureMessage(cause: unknown, picker = false) {
    const reason = cause instanceof Error ? cause.message : typeof cause === "string" ? cause : "";
    return reason.includes("preview_no_filesystem")
      ? "Abra o aplicativo instalado para verificar uma pasta. A demonstração no navegador não acessa seus arquivos."
      : picker ? "Não foi possível escolher a pasta. Tente novamente ou informe o caminho completo abaixo."
        : "Não foi possível adicionar a pasta. Informe um caminho local absoluto, existente e acessível.";
  }

  async function choose() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true); setChoosing(true); setError(null); setPathInvalid(false); setChosen(false);
    try {
      const project = await chooseDesktopProject();
      if (!mounted.current) return;
      if (project) {
        // A picker result is a path to review, not consent to add a bookmark.
        setPath(project.path);
        setChosen(true);
        focusAfterOperation.current = "path";
      } else {
        focusAfterOperation.current = "choose";
      }
    } catch (cause) {
      if (!mounted.current) return;
      setError(failureMessage(cause, true));
      focusAfterOperation.current = "choose";
    } finally {
      lock.current = false;
      if (mounted.current) { setBusy(false); setChoosing(false); }
    }
  }

  async function add() {
    if (lock.current || !path.trim()) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    setPathInvalid(false);
    try {
      const project = await validateDesktopProject(path.trim());
      if (!mounted.current) return;
      onAdd(project);
      onClose();
    } catch (cause) {
      if (!mounted.current) return;
      setError(failureMessage(cause));
      setPathInvalid(true);
      focusAfterOperation.current = "path";
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  return <dialog className="project-dialog" ref={dialog} aria-labelledby="add-project-heading" aria-describedby="add-project-description" onCancel={(event) => { event.preventDefault(); if (!lock.current) onClose(); }}>
    <div className="dialog-heading"><span className="project-emblem"><Glyph name="folder" size={24} /></span><button className="icon-button" type="button" onClick={onClose} disabled={busy} aria-label="Fechar"><Glyph name="close" size={18} /></button></div>
    <h2 id="add-project-heading">Adicionar projeto</h2>
    <p id="add-project-description">Vincule uma pasta existente a este Desktop. Nenhum arquivo será copiado ou alterado.</p>
    <form aria-busy={busy} onSubmit={(event) => { event.preventDefault(); void add(); }}>
      <button ref={chooseButton} className="button button-secondary project-picker" type="button" disabled={busy} aria-busy={choosing} onClick={() => void choose()}><Glyph name="folder" size={18} />{choosing ? "Escolhendo pasta…" : "Escolher pasta…"}</button>
      <p className="project-path-alternative">ou informe o caminho completo</p>
      <label className="workbench-field">Caminho da pasta
        <input ref={pathInput} value={path} onChange={(event) => { setPath(event.target.value); setError(null); setPathInvalid(false); setChosen(false); }} required maxLength={4096} disabled={busy} aria-invalid={pathInvalid} aria-describedby={error ? "project-path-hint project-path-error" : "project-path-hint"} autoComplete="off" spellCheck={false} placeholder="/caminho/do/projeto ou C:\projetos\meu-app" />
      </label>
      <p className="field-hint" id="project-path-hint">Escolha uma pasta ou cole seu caminho. Revise antes de adicionar; o Runtime verifica o destino novamente.</p>
      {chosen && <p className="project-chosen-note" role="status"><Glyph name="check" size={15} />Pasta escolhida. O projeto só será adicionado quando você confirmar.</p>}
      {choosing && <p className="field-hint" role="status">Conclua ou cancele a escolha na janela do sistema.</p>}
      {error && <p className="inline-error" id="project-path-error" role="alert">{error}</p>}
      <div className="dialog-actions"><button className="button button-secondary" type="button" disabled={busy} onClick={onClose}>Cancelar</button><button className="button button-primary" type="submit" disabled={busy || !path.trim()}>{busy ? "Verificando…" : "Adicionar projeto"}</button></div>
    </form>
  </dialog>;
}
