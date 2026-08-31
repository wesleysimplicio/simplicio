import { useEffect, useRef, useState } from "react";
import { chooseDesktopProject, loadDesktopUsageProjects } from "../bridge";
import { projectDiscoveryError, type UsageProjects } from "../project_usage";
import "../project_usage.css";

export function TokenProjects({ repoPath, allowAutoSelect, onSelect, onDiscovery }: {
  repoPath: string; allowAutoSelect: boolean; onSelect: (path: string) => void;
  onDiscovery?: (result: UsageProjects | null) => void;
}) {
  const [discovery, setDiscovery] = useState<UsageProjects | null>(null);
  const [busy, setBusy] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);
  const readLock = useRef(false);
  const pickerLock = useRef(false);
  const mounted = useRef(false);
  const latest = useRef({ repoPath, allowAutoSelect, onSelect, onDiscovery });
  latest.current = { repoPath, allowAutoSelect, onSelect, onDiscovery };

  async function discover() {
    if (readLock.current) return;
    readLock.current = true;
    const generation = ++request.current;
    setBusy(true); setError(null);
    try {
      const result = await loadDesktopUsageProjects();
      if (generation !== request.current) return;
      setDiscovery(result);
      latest.current.onDiscovery?.(result);
      if (latest.current.allowAutoSelect && !latest.current.repoPath.trim() && result.projects.length) {
        latest.current.onSelect(result.projects[0].path);
      }
    } catch (cause) {
      if (generation === request.current) { setError(projectDiscoveryError(cause)); latest.current.onDiscovery?.(null); }
    } finally {
      readLock.current = false;
      if (generation === request.current) setBusy(false);
    }
  }

  useEffect(() => { mounted.current = true; void discover(); return () => { mounted.current = false; request.current += 1; readLock.current = false; }; }, []);

  async function choose() {
    if (pickerLock.current) return;
    pickerLock.current = true;
    setChoosing(true); setError(null);
    try {
      const project = await chooseDesktopProject();
      if (project && mounted.current) latest.current.onSelect(project.path);
    } catch { if (mounted.current) setError("Não foi possível abrir ou validar a pasta. Informe o caminho manualmente abaixo."); }
    finally { pickerLock.current = false; if (mounted.current) setChoosing(false); }
  }

  const selected = discovery?.projects.find((project) => project.path === repoPath.trim());
  return <section className="panel token-projects" aria-label="Pastas com uso do Simplicio">
    <div className="token-projects-heading"><div><span className="eyebrow">Descoberta automática</span><h2>Pastas com registros do Simplicio</h2><p>Selecione um projeto encontrado para consultar seus relatórios. Os dados permanecem neste computador.</p></div><button className="button button-secondary" type="button" disabled={busy} onClick={() => void discover()}>{busy ? "Buscando pastas…" : "Atualizar pastas"}</button></div>
    <div className="token-projects-controls">
      <label>Projetos encontrados<select aria-label="Projetos com uso do Simplicio" value={selected?.id ?? ""} disabled={!discovery?.projects.length} onChange={(event) => {
        const project = discovery?.projects.find((item) => item.id === event.target.value);
        if (project) onSelect(project.path);
      }}><option value="">{busy ? "Procurando ledgers locais…" : "Selecione uma pasta"}</option>{discovery?.projects.map((project) => <option key={project.id} value={project.id}>{project.name} — {project.path}</option>)}</select></label>
      <button className="button button-secondary" type="button" disabled={choosing} onClick={() => void choose()}>{choosing ? "Escolhendo…" : "Escolher outra pasta…"}</button>
    </div>
    {error && <p className="token-projects-notice" aria-live="polite">{error}</p>}
    {discovery && <>
      <p>{discovery.projects.length} {discovery.projects.length === 1 ? "pasta encontrada" : "pastas encontradas"}. {selected && <>Nesta pasta: {selected.evidenceType === "both" ? "ledgers de contexto e uso" : selected.evidenceType === "context" ? "ledger de contexto" : "ledger de uso"}.</>}</p>
      <p className="token-projects-note">Um ledger encontrado é um candidato; o Runtime verifica o relatório antes de mostrar os números. A descoberta não lê os documentos do projeto.</p>
      {discovery.partial && <p className="token-projects-notice">Descoberta parcial: algum limite, pasta inacessível ou leitura sem resposta restringiu a busca. As pastas encontradas continuam disponíveis; use a seleção manual para outras.</p>}
      {!!discovery.unavailableRoots?.length && <p className="token-projects-note">Locais não concluídos: {discovery.unavailableRoots.map((name) => name === "Configured repository" ? "Repositório configurado" : name).join(", ")}. A escolha manual continua disponível.</p>}
      {!discovery.projects.length && <p>Nenhum ledger foi encontrado nesta busca. Escolha uma pasta manualmente para consultar outro local.</p>}
      <details><summary>Locais e limites da busca</summary><ul>{discovery.roots.map((root) => <li key={root.path}><strong>{root.name}</strong><code>{root.path}</code></li>)}</ul><p>Até 5 níveis, 4.000 diretórios e 64 resultados recentes. O orçamento é dividido entre os locais pesquisados. A busca não percorre a pasta pessoal inteira, não segue links simbólicos e ignora caches e dependências. Cada local é consultado em um processo separado com prazo de 3 segundos; se uma leitura não responder, os resultados dos outros locais são preservados.</p></details>
    </>}
  </section>;
}
