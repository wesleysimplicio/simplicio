import type { DesktopSnapshot } from "../contracts";
import { Glyph } from "../components/Brand";
import { createSettingsProjection } from "../settings_projection";
import type { WorkbenchPreferences, View } from "../workbench";

function Toggle({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: () => void }) {
  return <div className="preference-row"><div><strong>{label}</strong><p>{description}</p></div><button type="button" role="switch" aria-checked={checked} aria-label={label} className={"preference-switch" + (checked ? " checked" : "")} onClick={onChange}><span /></button></div>;
}

export function PreferencesScreen({ view, preferences, onPreferences, snapshot, onProviders }:
  { view: Extract<View, "general" | "shortcuts" | "models">; preferences: WorkbenchPreferences; onPreferences: (value: WorkbenchPreferences) => void; snapshot: DesktopSnapshot; onProviders: () => void }) {
  if (view === "shortcuts") return <div className="page preferences-page">
    <section className="page-heading"><div><h1>Atalhos</h1><p>Navegue pelo Desktop sem sair do teclado.</p></div></section>
    <section className="settings-section"><h2>Navegação</h2><div className="settings-slab">{[
      ["Buscar projetos, páginas ou configurações", "⌘ / Ctrl K"], ["Recolher ou expandir a barra lateral", "⌘ / Ctrl B"],
      ["Abrir configurações", "⌘ / Ctrl ,"], ["Voltar à página anterior", "Alt ←"],
      ["Avançar no histórico", "Alt →"], ["Fechar o diálogo de projeto", "Esc"],
    ].map(([label, key]) => <div className="preference-row" key={key}><strong>{label}</strong><kbd>{key}</kbd></div>)}</div><p className="settings-footnote">Use Tab para percorrer os controles e Enter ou Espaço para ativá-los. Durante a verificação de uma pasta, aguarde a conclusão antes de fechar o diálogo.</p></section>
  </div>;

  if (view === "models") {
    const inventory = createSettingsProjection(snapshot);
    return <div className="page preferences-page">
      <section className="page-heading"><div><h1>Modelos e skills</h1><p>Inventário informado pelo Runtime. Credenciais permanecem nos seus providers.</p></div></section>
      <section className="settings-section"><h2>Modelos / LLMs</h2><div className="settings-slab">
        {inventory.models.length ? inventory.models.map((model) => <div className="inventory-row" key={model.id}><Glyph name="spark" size={20} /><strong>{model.label}</strong><span className="neutral-badge">Somente leitura</span></div>) : <div className="inventory-empty"><Glyph name="spark" size={28} /><h3>Nenhum modelo foi informado pelo Runtime</h3><p>Login ativo ou MCP registrado não significa que um LLM esteja conectado. O inventário aparece quando o Agent Plane fornecer essa evidência.</p><button type="button" className="button button-secondary" onClick={onProviders}>Ver agentes e IDEs</button></div>}
      </div></section>
      <section className="settings-section"><h2>Ferramentas e skills</h2><div className="settings-slab">{inventory.tools.length || inventory.skills.length
        ? [...inventory.tools, ...inventory.skills].map((item) => <div className="inventory-row" key={item.id + item.reasonCode}><Glyph name="apps" size={18} /><strong>{item.label}</strong><span className="neutral-badge">Informado pelo Runtime</span></div>)
        : <div className="preference-row"><div><strong>Inventário ainda não disponível</strong><p>O Desktop não presume instalação nem execução de plugins. Revise o plano em Integrações MCP para configurar os clientes detectados.</p></div></div>}</div></section>
    </div>;
  }

  return <div className="page preferences-page">
    <section className="page-heading"><div><h1>Aparência</h1><p>Um espaço claro e organizado. Preferências salvas somente neste computador.</p></div></section>
    <section className="settings-section"><h2>Interface</h2><div className="settings-slab">
      <div className="preference-row"><div><strong>Tema claro</strong><p>Fundo branco em todas as telas, independente do tema do sistema.</p></div><span className="theme-swatch"><span /><Glyph name="check" size={16} />Claro</span></div>
      <div className="preference-row"><div><strong>Densidade da navegação</strong><p>Ajuste o espaçamento da lista de projetos e das categorias.</p></div><div className="segmented-control" role="group" aria-label="Densidade da navegação">{(["comfortable", "compact"] as const).map((density) => <button type="button" key={density} aria-pressed={preferences.density === density} className={preferences.density === density ? "active" : ""} onClick={() => onPreferences({ ...preferences, density })}>{density === "comfortable" ? "Confortável" : "Compacta"}</button>)}</div></div>
    </div></section>
    <section className="settings-section"><h2>Projetos</h2><div className="settings-slab">
      <Toggle label="Mostrar caminhos na lateral" description="Exibe o caminho local abaixo do nome de cada projeto." checked={preferences.showProjectPaths} onChange={() => onPreferences({ ...preferences, showProjectPaths: !preferences.showProjectPaths })} />
      <Toggle label="Lembrar o último projeto" description="Restaura a pasta selecionada quando você abrir o app novamente." checked={preferences.rememberProject} onChange={() => onPreferences({ ...preferences, rememberProject: !preferences.rememberProject })} />
    </div></section>
    <p className="settings-footnote"><Glyph name="lock" size={15} />Estas preferências não alteram permissões, modelos, configuração MCP ou execução de agentes.</p>
  </div>;
}
