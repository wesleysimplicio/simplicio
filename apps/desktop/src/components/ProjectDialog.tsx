import { useEffect, useRef, useState } from "react";
import { validateDesktopProject } from "../bridge";
import { Glyph } from "./Brand";
import type { LocalProject } from "../workbench";

export function ProjectDialog({ onClose, onAdd }: { onClose: () => void; onAdd: (project: LocalProject) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pathInput = useRef<HTMLInputElement>(null);
  const lock = useRef(false);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dialog.current?.showModal();
    pathInput.current?.focus();
  }, []);

  async function add() {
    if (lock.current || !path.trim()) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      onAdd(await validateDesktopProject(path.trim()));
      onClose();
    } catch (cause) {
      setError(String(cause).includes("preview_no_filesystem")
        ? "Abra o aplicativo instalado para verificar uma pasta. A demonstração no navegador não acessa seus arquivos."
        : "Não foi possível adicionar a pasta. Informe um caminho local absoluto, existente e acessível.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return <dialog className="project-dialog" ref={dialog} aria-labelledby="add-project-heading" onCancel={(event) => { event.preventDefault(); if (!lock.current) onClose(); }}>
    <div className="dialog-heading"><span className="project-emblem"><Glyph name="folder" size={24} /></span><button className="icon-button" type="button" onClick={onClose} disabled={busy} aria-label="Fechar"><Glyph name="close" size={18} /></button></div>
    <h2 id="add-project-heading">Adicionar projeto</h2>
    <p>Vincule uma pasta existente a este Desktop. Nenhum arquivo será copiado ou alterado.</p>
    <form onSubmit={(event) => { event.preventDefault(); void add(); }}>
      <label className="workbench-field">Caminho da pasta
        <input ref={pathInput} value={path} onChange={(event) => setPath(event.target.value)} required maxLength={4096} disabled={busy} autoComplete="off" spellCheck={false} placeholder="/caminho/do/projeto ou C:\projetos\meu-app" />
      </label>
      <p className="field-hint">Cole o caminho completo da pasta. O aplicativo verifica se ela existe antes de adicioná-la.</p>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="dialog-actions"><button className="button button-secondary" type="button" disabled={busy} onClick={onClose}>Cancelar</button><button className="button button-primary" type="submit" disabled={busy || !path.trim()}>{busy ? "Verificando…" : "Adicionar projeto"}</button></div>
    </form>
  </dialog>;
}
