import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { DesktopSnapshot, ProviderConnection } from "../contracts";
import { Glyph, type GlyphName } from "../components/Brand";
import { providerRegistry } from "../provider_registry";
import { createSettingsProjection } from "../settings_projection";
import { REFERENCE_SCREENS, type ReferenceSettingsView } from "../reference_screens";
import { searchMatches, type View } from "../workbench";
import "../reference_settings.css";

export interface ReferenceSettingsProps {
  view: ReferenceSettingsView;
  snapshot: DesktopSnapshot;
  onNavigate: (view: View) => void;
  onRefresh?: () => void;
  busy?: boolean;
}

export const REFERENCE_QUICK_COMMANDS = {
  version: { label: "Versão do Runtime", command: "simplicio version", description: "Consulta a versão do executável encontrado no seu terminal." },
  access: { label: "Estado da conta", command: "simplicio auth status --json", description: "Consulta a autenticação do Runtime. Não inicia um novo login." },
  plugins: { label: "Registry de plugins", command: "simplicio plugin list --json", description: "Lista o registry do Runtime; não comprova os pacotes nativos de cada IDE." },
  plan: { label: "Prévia de integração", command: "simplicio install --global --dry-run --json", description: "Mostra o plano MCP/hooks sem aplicar alterações." },
} as const;
type CommandId = keyof typeof REFERENCE_QUICK_COMMANDS;
type CopyOutcome = "copied" | "unavailable" | "uncertain" | "cancelled";

/** Only copies allowlisted text. It never executes a command or reads the clipboard. */
export function copyReferenceCommand(id: CommandId, write: ((text: string) => Promise<void>) | undefined, signal?: AbortSignal): Promise<CopyOutcome> {
  if (signal?.aborted) return Promise.resolve("cancelled");
  if (!Object.prototype.hasOwnProperty.call(REFERENCE_QUICK_COMMANDS, id) || !write) return Promise.resolve("unavailable");
  return new Promise((resolve) => {
    let settled = false;
    const finish = (outcome: CopyOutcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", cancelled);
      resolve(outcome);
    };
    const cancelled = () => finish("cancelled");
    const timer = setTimeout(() => finish("uncertain"), 4000);
    signal?.addEventListener("abort", cancelled, { once: true });
    Promise.resolve().then(() => {
      if (signal?.aborted) { finish("cancelled"); return; }
      return write(REFERENCE_QUICK_COMMANDS[id].command);
    }).then(() => finish(signal?.aborted ? "cancelled" : "copied"), () => finish("unavailable"));
  });
}

function metadataLabel(value: unknown, fallback: string, maximum = 140): string {
  if (typeof value !== "string") return fallback;
  const clean = value.replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, "").trim();
  if (!clean || /^(?:\/|[a-z]:[\\/])/i.test(clean) || /(?:pypi-|gh[pousr]_|sk-)[a-z0-9_-]{16}/i.test(clean)) return fallback;
  return clean.slice(0, maximum);
}

function observedTime(value: unknown): string {
  if (typeof value !== "string" || value.length > 40 || !/^\d{4}-\d{2}-\d{2}T/.test(value)) return "Data não informada";
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString("pt-BR") : "Data não informada";
}

/** This projection deliberately excludes identities, prompts, config bodies, URLs and local paths. */
export function createReferenceSettingsEvidence(snapshot: DesktopSnapshot) {
  const runtime = snapshot.source === "runtime";
  const center = runtime && snapshot.botCenter?.source === "runtime" ? snapshot.botCenter : undefined;
  const inventory = createSettingsProjection(snapshot);
  return {
    source: snapshot.source,
    observedAt: observedTime(snapshot.generatedAt),
    runtimeVersion: runtime ? metadataLabel(snapshot.runtime.version, "Não informada", 48) : "Não verificada na prévia",
    runtimeState: runtime ? ({ healthy: "Saudável", starting: "Iniciando", degraded: "Degradado", offline: "Offline" }[snapshot.runtime.state] ?? "Não informado") : "Prévia",
    transport: runtime ? ({ sidecar: "Executável local", daemon: "Daemon", unavailable: "Indisponível" }[snapshot.runtime.transport] ?? "Não informado") : "Não verificado",
    providers: runtime ? providerRegistry(snapshot.providers.slice(0, 32)).map((provider) => ({
      id: provider.id, name: metadataLabel(provider.name, "Cliente"), state: provider.state,
      protocol: provider.protocol, registrationState: provider.registrationState,
    })) : [],
    models: inventory.models.slice(0, 32).map((item) => metadataLabel(item.label, "Modelo não informado")),
    skills: inventory.skills.slice(0, 128).map((item) => metadataLabel(item.label, "Skill não informada")),
    tools: inventory.tools.slice(0, 128).map((item) => metadataLabel(item.label, "Ferramenta não informada")),
    bots: center?.bots.slice(0, 32).map((bot) => ({
      name: metadataLabel(bot.displayName, "Agente"), lifecycle: bot.lifecycle,
      model: metadataLabel(bot.model, "Modelo não informado"), profile: metadataLabel(bot.agentProfileId, "Perfil não informado"),
    })) ?? [],
    computer: center ? {
      available: center.computer.available,
      state: center.computer.state,
      observedAt: observedTime(center.computer.lastEventAt),
    } : null,
    artifacts: center?.sessions.slice(0, 32).flatMap((session) => session.events.slice(0, 200))
      .filter((event) => event.kind === "artifact").slice(0, 64).map((event) => ({
        name: metadataLabel(event.artifactName, "Artefato informado"),
        observedAt: observedTime(event.timestamp),
        state: event.state,
      })) ?? [],
  };
}
type Evidence = ReturnType<typeof createReferenceSettingsEvidence>;
type Navigate = ReferenceSettingsProps["onNavigate"];

function Badge({ children, positive = false }: { children: ReactNode; positive?: boolean }) {
  return <span className={"ref-badge" + (positive ? " ref-badge-positive" : "")}>{children}</span>;
}

function Section({ title, description, children, action }: { title: string; description?: string; children: ReactNode; action?: ReactNode }) {
  return <section className="ref-section"><div className="ref-section-heading"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div><div className="ref-slab">{children}</div></section>;
}

function Row({ title, description, children, icon }: { title: string; description?: ReactNode; children?: ReactNode; icon?: GlyphName }) {
  return <div className="ref-row">{icon && <span className="ref-row-icon"><Glyph name={icon} size={20} /></span>}<div className="ref-row-copy"><strong>{title}</strong>{description && <p>{description}</p>}</div>{children && <div className="ref-row-control">{children}</div>}</div>;
}

function Unavailable({ label, reason }: { label: string; reason: string }) {
  const id = useId();
  return <div className="ref-unavailable-control"><button type="button" className="button button-secondary" disabled aria-describedby={id}>{label}</button><small id={id}>{reason}</small></div>;
}

function UnavailableSwitch({ label, reason }: { label: string; reason: string }) {
  const id = useId();
  return <div className="ref-unavailable-control"><button type="button" className="preference-switch ref-disabled-switch" role="switch" aria-checked={false} aria-label={label} disabled aria-describedby={id}><span /></button><small id={id}>{reason}</small></div>;
}

function UnavailableSelect({ label, value = "Não disponível" }: { label: string; value?: string }) {
  return <select aria-label={label} className="workbench-select" disabled value=""><option value="">{value}</option></select>;
}

function LinkButton({ children, to, onNavigate, icon = "arrow" }: { children: ReactNode; to: View; onNavigate: Navigate; icon?: GlyphName }) {
  return <button type="button" className="button button-secondary" onClick={() => onNavigate(to)}>{children}<Glyph name={icon} size={16} /></button>;
}

function Notice({ children, title = "Disponibilidade neste Desktop" }: { title?: string; children: ReactNode }) {
  return <aside className="ref-notice"><Glyph name="shield" size={19} /><div><strong>{title}</strong><p>{children}</p></div></aside>;
}

function CommandCard({ id }: { id: CommandId }) {
  const item = REFERENCE_QUICK_COMMANDS[id];
  const [state, setState] = useState<CopyOutcome | "idle" | "copying">("idle");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  async function copy() {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    setState("copying");
    let write: ((text: string) => Promise<void>) | undefined;
    try {
      const clipboard = typeof navigator === "undefined" ? undefined : navigator.clipboard;
      write = clipboard && typeof clipboard.writeText === "function" ? clipboard.writeText.bind(clipboard) : undefined;
    } catch { /* A denied clipboard API must leave a usable manual-copy path. */ }
    const outcome = await copyReferenceCommand(id, write, controller.signal);
    if (active.current !== controller) return;
    active.current = null;
    if (outcome !== "cancelled") setState(outcome);
  }
  return <article className="ref-command-card"><h3>{item.label}</h3><p>{item.description}</p><div className="ref-command-line"><code>{item.command}</code><button className="button button-secondary" type="button" onClick={() => void copy()} disabled={state === "copying"} aria-label={"Copiar " + item.label}>{state === "copying" ? "Copiando…" : state === "copied" ? "Copiado" : "Copiar"}</button></div>
    <span className="ref-copy-status" role="status">{state === "copied" ? "Comando copiado. Nenhum comando foi executado." : state === "unavailable" ? "Não foi possível copiar. Selecione o comando e copie manualmente." : state === "uncertain" ? "Não foi possível confirmar a cópia. Confira a área de transferência ou copie manualmente." : ""}</span>
  </article>;
}

const providerStateLabels: Record<ProviderConnection["state"], string> = {
  connected: "Handshake MCP confirmado", registered: "MCP registrado", detected: "Cliente detectado",
  needs_attention: "MCP requer atenção", not_installed: "Cliente não encontrado",
};

function Accounts({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  const accounts = [
    { id: "claude-code", name: "Claude", mark: "CL", description: "A autenticação do Claude Code continua sob controle do próprio agente." },
    { id: "codex", name: "Codex", mark: "CX", description: "Seu cliente Codex administra contas e credenciais; o Simplicio não importa tokens." },
    { id: "gemini", name: "Gemini", mark: "GE", description: "O login do Gemini CLI não é reutilizado automaticamente como uma conta do Desktop." },
    { id: "opencode", name: "OpenCode", mark: "OC", description: "Contas, modelos e chaves permanecem na configuração do OpenCode." },
  ];
  return <>
    <Notice title="Contas do provedor são separadas da conta Simplicio">Registro MCP, cliente instalado e autenticação do provedor são evidências diferentes. Nenhuma credencial será solicitada, importada ou armazenada aqui.</Notice>
    {accounts.map((account) => {
      const provider = evidence.providers.find((item) => item.id === account.id);
      return <section className="ref-account-card" key={account.id}><div className="ref-account-heading"><span className={"ref-monogram ref-monogram-" + account.id}>{account.mark}</span><div><h2>{account.name}</h2><p>{account.description}</p></div></div>
        <Row title="Contas neste dispositivo" description="O inventário atual não informa contas gerenciadas deste provedor."><Unavailable label={"Adicionar conta " + account.name} reason="Gerenciamento de contas ainda indisponível." /></Row>
        <div className="ref-account-default"><div><strong>Autenticação no cliente</strong><p>Identidade e sessão não consultadas pelo Desktop.</p></div><Badge>Não verificada</Badge></div>
        <div className="ref-account-evidence"><span>{provider ? providerStateLabels[provider.state] : "Cliente não informado nesta consulta"}</span><button type="button" className="text-button" onClick={() => onNavigate("agents")}>Ver agente e IDE</button></div>
      </section>;
    })}
    <Section title="Outros provedores" description="Integrações adicionais continuam pertencendo ao cliente de IA."><Row title="MiniMax e provedores personalizados" description="Cookies de sessão e chaves de API não são coletados nesta tela."><Unavailable label="Configurar provedor" reason="Falta um contrato seguro de autenticação." /></Row></Section>
    <LinkButton to="settings" onNavigate={onNavigate}>Abrir conta Simplicio</LinkButton>
  </>;
}

const reviewServices = [
  { name: "GitHub", mark: "GH", description: "Pull requests, issues e revisão de código." },
  { name: "GitLab", mark: "GL", description: "Merge requests, issues e projetos GitLab." },
  { name: "Bitbucket", mark: "BB", description: "Repositórios e pull requests do Bitbucket." },
  { name: "Azure DevOps", mark: "AZ", description: "Código-fonte, work items e revisões." },
  { name: "Gitea", mark: "GT", description: "Repositórios e revisão em servidores Gitea." },
];
const taskServices = [
  { name: "Linear", mark: "LI", description: "Issues, equipes e contexto de tarefas." },
  { name: "Jira", mark: "JI", description: "Projetos e tarefas do Jira." },
];

function ServiceCards({ services }: { services: typeof reviewServices }) {
  return <div className="ref-service-stack">{services.map((service) => <article className="ref-service-card" key={service.name}><div className="ref-service-top"><span className="ref-monogram">{service.mark}</span><div><h3>{service.name}</h3><p>{service.description}</p></div><Badge>Não verificado</Badge></div><div className="ref-service-bottom"><p>O Runtime ainda não fornece ao Desktop uma consulta de conta e um fluxo de conexão para este serviço.</p><Unavailable label={"Conectar " + service.name} reason="Conexão nativa indisponível." /></div></article>)}</div>;
}

function Integrations({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice>Esta é a área de serviços externos. O estado de GitHub, Linear ou Jira não é inferido de um agente conectado ao MCP.</Notice>
    <Section title="Revisão e código-fonte" description="Provedores para acompanhar repositórios e revisões."><ServiceCards services={reviewServices} /></Section>
    <Section title="Provedores de tarefas" description="Contas e permissões precisam ser verificadas pelo serviço."><ServiceCards services={taskServices} /></Section>
    <div className="ref-action-row"><LinkButton to="task-sources" onNavigate={onNavigate}>Ver fontes de tarefas</LinkButton><LinkButton to="providers" onNavigate={onNavigate}>Configurar integrações MCP</LinkButton></div>
  </>;
}

function Orchestration({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Simplicio Loop" description="Os agentes executam dentro da autoridade do Runtime, não de uma preferência visual.">
      <Row title="Execução governada" icon="automation" description="Planos, consentimento e evidências continuam no fluxo do Runtime."><LinkButton to="bot" onNavigate={onNavigate}>Abrir Bot Center</LinkButton></Row>
      <Row title="Paralelismo sob demanda" description="O limite de paralelismo não foi consultado nesta tela. A capacidade disponível e a admissão de agentes dependem das políticas do Runtime."><Badge>Limite não consultado</Badge></Row>
      <Row title="Agente e modelo padrão" description="Nenhum modelo é selecionado automaticamente por esta tela."><UnavailableSelect label="Agente e modelo padrão" value="Gerenciado no Runtime" /></Row>
    </Section>
    <Section title="Perfis informados" description="Inventário da última consulta, sem inferir trabalho em execução.">
      {evidence.bots.length ? evidence.bots.map((bot, index) => <Row key={index} title={bot.name} description={bot.profile + " · " + bot.model} icon="teams"><Badge>{({ disabled: "Desativado", idle: "Ocioso", active: "Ativo no registro", busy: "Ocupado no registro", degraded: "Degradado", blocked: "Bloqueado" })[bot.lifecycle]}</Badge></Row>) : <Row title="Sem inventário de agentes nesta consulta" description="Abra o Bot Center para consultar a disponibilidade do Agent Plane." />}
    </Section>
    <Section title="Autonomia e aprovação"><Row title="Aprovar ações automaticamente" description="A política do Runtime não pode ser ampliada por uma opção da interface."><UnavailableSwitch label="Aprovar ações automaticamente" reason="Aprovações não são alteradas aqui." /></Row><Row title="Recuperação de tarefas" description="Retomada, interrupção e cancelamento exigem uma sessão e uma ação oferecida pelo Runtime."><LinkButton to="activity" onNavigate={onNavigate}>Ver atividade</LinkButton></Row></Section>
  </>;
}

function Computer({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  const computer = evidence.computer;
  const state = computer ? ({ bot_control: "Controle do bot informado", human_control: "Controle humano informado", paused: "Pausado no registro", blocked: "Bloqueado no registro" })[computer.state] : "Sessão não informada";
  return <>
    <div className="ref-status-banner"><Glyph name="monitor" size={25} /><div><h2>{computer?.available ? "Controle informado pelo Runtime" : "Controle do computador não confirmado"}</h2><p>{state}. Permissões do sistema são verificadas separadamente.</p></div><Badge>{computer?.available ? "Registro disponível" : "Não verificado"}</Badge></div>
    <Section title="Permissões necessárias"><Row title="Acessibilidade" icon="shield" description="Inspeção de interfaces e ações em janelas. O Desktop ainda não consulta essa permissão."><Badge>Não consultada</Badge></Row><Row title="Capturas de tela" icon="monitor" description="Captura de janelas para inspeção visual. Nenhuma captura é feita por esta tela."><Badge>Não consultada</Badge></Row><Row title="Acesso do sistema" description="Revise os requisitos antes de permitir automação de aplicativos."><LinkButton to="permissions" onNavigate={onNavigate}>Ver permissões</LinkButton></Row></Section>
    <Section title="Ferramentas de Computer Use"><Row title="Skill e sessão" description="Um nome no inventário não comprova skill instalada, permissões concedidas ou controle ativo."><LinkButton to="models" onNavigate={onNavigate}>Ver ferramentas e skills</LinkButton></Row><Row title="Controlar o computador" description="Ações só aparecem no Bot Center quando uma sessão real as autoriza."><LinkButton to="bot" onNavigate={onNavigate}>Abrir controle no Bot Center</LinkButton></Row></Section>
  </>;
}

function Voice({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice title="Áudio não conectado nesta versão do Desktop">Não há contrato nativo de captura e transcrição exposto a esta tela. Nenhum microfone é aberto e nenhum modelo é baixado.</Notice>
    <Section title="Ditado"><Row title="Ativar ditado por voz" description="Transcrever fala para o campo de texto em foco."><UnavailableSwitch label="Ativar ditado por voz" reason="Captura de áudio indisponível." /></Row><Row title="Modo de ditado" description="Alternar a gravação ou manter uma tecla pressionada."><div className="ref-disabled-segments" role="group" aria-label="Modo de ditado"><button disabled type="button">Alternar</button><button disabled type="button">Manter pressionado</button></div></Row><Row title="Microfone" description="Nenhum dispositivo foi consultado."><UnavailableSelect label="Microfone" value="Dispositivos não consultados" /></Row></Section>
    <Section title="Modelo de voz"><Row title="Reconhecimento de fala" description="Instalação, tamanho e compatibilidade precisam ser fornecidos pelo Runtime."><UnavailableSelect label="Modelo de voz" value="Inventário não disponível" /></Row><Row title="Idioma e processamento local" description="Nenhum idioma, provedor ou modo offline é presumido pelo Desktop."><Badge>Não configurável</Badge></Row></Section>
    <LinkButton to="permissions" onNavigate={onNavigate}>Ver permissões de microfone</LinkButton>
  </>;
}

function Mobile({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice title="Pareamento ainda indisponível">O Desktop não possui um contrato de Simplicio Mobile, relay ou tokens de pareamento. Não é gerado QR code de demonstração.</Notice>
    <Section title="Parear um dispositivo" description="A conexão precisa de identidade, expiração e revogação verificáveis.">
      <div className="ref-pairing-layout"><div className="ref-pairing-steps"><div><span>1</span><p><strong>Aplicativo compatível</strong>Um cliente mobile precisa ser publicado e identificado pelo Runtime.</p></div><div><span>2</span><p><strong>Canal autorizado</strong>LAN ou relay devem oferecer um transporte autenticado.</p></div><div><span>3</span><p><strong>Confirmação do dispositivo</strong>O código só pode existir com validade e revogação reais.</p></div></div><div className="ref-pairing-empty"><Glyph name="lock" size={36} /><strong>Pareamento não disponível</strong><span>Nenhum código emitido</span></div></div>
      <Row title="Conexão" description="Nenhum endereço local ou servidor é descoberto nesta tela."><UnavailableSelect label="Conexão mobile" value="LAN / relay indisponíveis" /></Row><Row title="Código de pareamento" description="O código deve ser pessoal, temporário e revogável."><Unavailable label="Gerar QR code" reason="Falta o contrato de pareamento." /></Row>
    </Section>
    <Section title="Dispositivos pareados"><Row title="Inventário não disponível" description="Isso não confirma a ausência de dispositivos pareados em outros clientes." /><Row title="Ao sair do aplicativo mobile" description="Restauração de terminal e tamanho da sessão dependem do cliente mobile."><UnavailableSelect label="Comportamento ao sair do mobile" /></Row></Section>
    <LinkButton to="servers" onNavigate={onNavigate}>Ver servidores Simplicio</LinkButton>
  </>;
}

function General({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Aplicativo"><Row title="Simplicio" icon="settings" description="Configurações locais da interface e identidade do aplicativo."><LinkButton to="settings" onNavigate={onNavigate}>Minha conta</LinkButton></Row><Row title="Aparência e navegação" description="Tema branco, densidade e atalhos de projeto são ajustados na tela Aparência."><LinkButton to="general" onNavigate={onNavigate}>Ajustar aparência</LinkButton></Row><Row title="Ao iniciar" description="A lembrança do último projeto é uma preferência local já disponível."><LinkButton to="general" onNavigate={onNavigate}>Preferências de início</LinkButton></Row></Section>
    <Section title="Ambiente"><Row title="Runtime" description={"Versão informada: " + evidence.runtimeVersion}><Badge>{evidence.runtimeState}</Badge></Row><Row title="Inicializar junto com o sistema" description="Nenhum serviço de inicialização automática é alterado pelo Desktop."><UnavailableSwitch label="Inicializar junto com o sistema" reason="Ação nativa indisponível." /></Row><Row title="Atualizações do Desktop" description="Use Check for Updates… no menu. A consulta procura um pacote compatível; a instalação continua manual."><Badge>Consulta de metadados</Badge></Row></Section>
  </>;
}

function Artifacts({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Artefatos informados" description="Somente nomes e datas fornecidos pelo Agent Plane. O Desktop não lê o conteúdo dos arquivos.">
      {evidence.artifacts.length ? <div className="ref-table-wrap"><table className="ref-table"><caption>Metadados da última consulta</caption><thead><tr><th>Artefato</th><th>Registro</th><th>Estado reportado</th></tr></thead><tbody>{evidence.artifacts.map((artifact, index) => <tr key={index}><td><Glyph name="folder" size={17} />{artifact.name}</td><td>{artifact.observedAt}</td><td>{artifact.state === "complete" ? "Concluído no registro" : artifact.state === "streaming" ? "Em produção no registro" : "Bloqueado"}</td></tr>)}</tbody></table></div> : <div className="ref-empty"><Glyph name="folder" size={30} /><h3>Nenhum artefato informado nesta consulta</h3><p>A ausência de metadados não significa que seus arquivos foram removidos.</p></div>}
      <Row title="Abrir ou exportar arquivos" description="O inventário não fornece um contrato de acesso verificado aos arquivos."><Unavailable label="Exportar artefatos" reason="Acesso nativo ainda indisponível." /></Row>
    </Section>
    <div className="ref-link-grid"><LinkButton to="bot" onNavigate={onNavigate}>Ver sessões no Bot Center</LinkButton><LinkButton to="tokens" onNavigate={onNavigate}>Abrir relatório de tokens</LinkButton><LinkButton to="activity" onNavigate={onNavigate}>Ver atividade do Runtime</LinkButton></div>
  </>;
}

function Skills({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Skills informadas pelo Runtime" description="Este é um inventário de nomes, não uma autorização para compartilhar arquivos.">
      {evidence.skills.length ? evidence.skills.map((skill, index) => <Row key={index} title={skill} icon="spark" description="Conteúdo e instruções da skill não são expostos nesta tela."><Badge>Informada</Badge></Row>) : <Row title="Inventário ainda não disponível" description="O Agent Plane não informou skills para esta consulta." />}
    </Section>
    <Section title="Compartilhamento"><Row title="Compartilhar entre projetos" description="Destino, licença, conteúdo e revisão precisam de um plano explícito."><UnavailableSwitch label="Compartilhar skills automaticamente" reason="Nenhum compartilhamento automático." /></Row><Row title="Publicar uma skill" description="Sem envio de conteúdo, prompts ou configurações a serviços externos."><Unavailable label="Compartilhar skill" reason="Publicação não disponível no Desktop." /></Row></Section>
    <div className="ref-action-row"><LinkButton to="plugins" onNavigate={onNavigate}>Ver pacotes de plugins</LinkButton><LinkButton to="models" onNavigate={onNavigate}>Ver modelos e ferramentas</LinkButton></div>
  </>;
}

function Git({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Projetos e repositórios"><Row title="Pastas locais" icon="folder" description="Adicione uma pasta existente pelo seletor nativo. Um atalho local não cria worktree nem clona repositórios."><LinkButton to="home" onNavigate={onNavigate}>Abrir projetos</LinkButton></Row><Row title="Repositório padrão" description="O contexto de cada projeto é escolhido explicitamente; nenhuma pasta é inferida aqui."><UnavailableSelect label="Repositório padrão" value="Selecione no projeto" /></Row></Section>
    <Section title="Revisão e alterações"><Row title="Status, diff e branches" description="Esta versão não oferece comandos Git mutantes nesta tela."><Unavailable label="Abrir revisão Git" reason="Contrato de revisão ainda indisponível." /></Row><Row title="Commit e push automático" description="Nenhuma alteração de repositório é autorizada ao visitar configurações."><UnavailableSwitch label="Commit e push automático" reason="Operação não disponível." /></Row></Section>
    <Section title="Serviços de código-fonte"><Row title="GitHub, GitLab e outros hosts" description="Login no Simplicio não autentica um serviço Git."><LinkButton to="integrations" onNavigate={onNavigate}>Ver integrações de serviços</LinkButton></Row></Section>
  </>;
}

function TaskSources({ onNavigate }: { onNavigate: Navigate }) {
  const services = [reviewServices[0], reviewServices[1], ...taskServices];
  return <>
    <Section title="Configurar origem das tarefas" description="Autenticação, consulta e visibilidade devem ser verificadas por provedor.">
      <div className="ref-source-list">{services.map((service) => <details className="ref-source-details" key={service.name}><summary><span className="ref-monogram">{service.mark}</span><span><strong>{service.name}</strong><small>{service.description}</small></span><Badge>Consulta indisponível</Badge><Glyph name="chevron" size={16} /></summary><div className="ref-source-body"><p>O Desktop ainda não recebe tarefas deste serviço. Mostrar uma categoria não estabelece conexão nem importa issues.</p><Row title={"Mostrar tarefas de " + service.name} description="Nenhuma preferência sem efeito é salva."><UnavailableSwitch label={"Mostrar tarefas de " + service.name} reason="Falta a consulta do provedor." /></Row><LinkButton to="integrations" onNavigate={onNavigate}>Ver conexão do serviço</LinkButton></div></details>)}</div>
    </Section>
    <Notice title="Nenhuma tarefa importada automaticamente">Ações de leitura, criação e edição de issues continuarão separadas. Os projetos e a atividade já disponíveis podem ser consultados sem conectar um serviço.</Notice>
    <LinkButton to="activity" onNavigate={onNavigate}>Ver atividade disponível</LinkButton>
  </>;
}

function Terminal({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Terminal local"><div className="ref-terminal-intro"><span className="ref-terminal-symbol" aria-hidden="true">&gt;_</span><div><h3>O Simplicio CLI continua no seu terminal</h3><p>Este painel não inicia um shell, não executa comandos e não lê histórico do terminal.</p></div></div><Row title="Terminal integrado" description="Uma sessão precisa de processo supervisionado, entrada/saída e cancelamento verificáveis."><Unavailable label="Abrir terminal integrado" reason="Sessão PTY não exposta ao Desktop." /></Row><Row title="Shell padrão" description="O shell do sistema não foi consultado."><UnavailableSelect label="Shell padrão" value="Não consultado" /></Row></Section>
    <Section title="Consultar o Runtime"><CommandCard id="version" /><CommandCard id="plan" /></Section>
    <LinkButton to="quick-commands" onNavigate={onNavigate}>Ver todos os comandos de consulta</LinkButton>
  </>;
}

function QuickCommands() {
  return <>
    <Notice title="Copiar não executa">Os comandos abaixo são fixos e documentados. Cole no seu terminal quando quiser executá-los. A saída permanece no terminal; esta tela não a coleta.</Notice>
    <Section title="Consultas do Simplicio">{(Object.keys(REFERENCE_QUICK_COMMANDS) as CommandId[]).map((id) => <CommandCard key={id} id={id} />)}</Section>
    <Section title="Comandos personalizados"><Row title="Adicionar atalho de execução" description="Comandos arbitrários não são armazenados nem executados pela interface."><Unavailable label="Adicionar comando" reason="Execução personalizada indisponível." /></Row></Section>
  </>;
}

function Browser({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Navegação por agentes"><Row title="Automação de navegador" description="O Desktop não inicia sessões de browser nem pressupõe acesso aos seus logins."><UnavailableSwitch label="Automação de navegador" reason="Contrato de sessão não disponível." /></Row>
      <div className="ref-browser-steps"><article><span>1</span><div><h3>Runtime e ferramentas</h3><p>Consulte o inventário; disponibilidade de ferramentas não confirma uma sessão de navegador.</p><LinkButton to="models" onNavigate={onNavigate}>Ver ferramentas</LinkButton></div></article><article><span>2</span><div><h3>Controle e permissões</h3><p>Uma sessão de Computer Use depende de autoridade explícita e acesso do sistema.</p><LinkButton to="computer-use" onNavigate={onNavigate}>Ver uso do computador</LinkButton></div></article><article><span>3</span><div><h3>Sessão autenticada</h3><p>Nenhum cookie, perfil ou senha é importado por esta tela.</p><Unavailable label="Importar cookies" reason="Importação não disponível." /></div></article></div>
    </Section>
    <Section title="Preferências do navegador"><Row title="Página inicial" description="Sem navegador integrado, nenhum endereço é salvo como preferência."><UnavailableSelect label="Página inicial do navegador" /></Row><Row title="Mecanismo de busca" description="O Desktop não modifica as configurações do seu navegador."><UnavailableSelect label="Mecanismo de busca" /></Row><Row title="Zoom padrão" description="Um valor só terá efeito após existir uma sessão de browser."><UnavailableSelect label="Zoom padrão do navegador" /></Row><Row title="Abrir links dentro do app" description="Login e releases usam os fluxos externos já oferecidos pelo Desktop."><UnavailableSwitch label="Abrir links dentro do app" reason="Navegador integrado indisponível." /></Row></Section>
  </>;
}

function Emulator({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Dispositivos de desenvolvimento"><div className="ref-device-grid">{["Android", "iOS"].map((platform) => <article key={platform} className="ref-device-card"><Glyph name="monitor" size={31} /><h3>{platform}</h3><Badge>Inventário não consultado</Badge><p>Nenhum SDK, simulador ou imagem de dispositivo foi detectado por esta tela.</p><Unavailable label={"Iniciar emulador " + platform} reason="Inicialização nativa indisponível." /></article>)}</div></Section>
    <Section title="Ambiente de teste"><Row title="Dispositivo padrão" description="A lista precisa ser fornecida por uma consulta nativa."><UnavailableSelect label="Dispositivo de emulação" value="Nenhum inventário disponível" /></Row><Row title="Capturar tela e inspecionar" description="Permissões e alvo precisam ser identificados antes de qualquer captura."><LinkButton to="computer-use" onNavigate={onNavigate}>Ver uso do computador</LinkButton></Row></Section>
  </>;
}

function Floating({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Espaço de trabalho"><div className="ref-window-layout" aria-label="Organização da janela principal"><span>Projetos</span><div><strong>Simplicio</strong><p>Uma janela principal, com navegação e contexto do projeto.</p></div></div><Row title="Abrir janela flutuante" description="Criação de janelas, foco e encerramento ainda não possuem um contrato nesta tela."><Unavailable label="Abrir janela flutuante" reason="Nova janela nativa indisponível." /></Row><Row title="Manter sempre à frente" description="Nenhuma preferência sem efeito é aplicada à janela atual."><UnavailableSwitch label="Manter janela sempre à frente" reason="Ação de janela indisponível." /></Row></Section>
    <Section title="Navegação disponível"><Row title="Lateral e densidade" description="Organize a janela principal com as preferências locais existentes."><LinkButton to="general" onNavigate={onNavigate}>Ajustar aparência</LinkButton></Row><Row title="Controle por teclado" description="Alternar a lateral, buscar e navegar sem sair do teclado."><LinkButton to="shortcuts" onNavigate={onNavigate}>Ver atalhos</LinkButton></Row></Section>
  </>;
}

function Input({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Navegação por teclado"><Row title="Percorrer controles" description="Use Tab e Shift + Tab para avançar e voltar entre controles disponíveis."><kbd>Tab</kbd></Row><Row title="Confirmar uma ação" description="Enter ou Espaço ativa o controle em foco."><kbd>Enter / Espaço</kbd></Row><Row title="Busca do aplicativo" description="A busca de navegação e projetos respeita os atalhos do Desktop."><LinkButton to="shortcuts" onNavigate={onNavigate}>Abrir atalhos</LinkButton></Row></Section>
    <Section title="Edição"><Row title="Editor de código padrão" description="Integrações MCP não alteram o editor padrão do sistema."><UnavailableSelect label="Editor padrão" value="Não configurável nesta tela" /></Row><Row title="Autoformatação" description="Formatação automática exige um editor e uma configuração de projeto."><UnavailableSwitch label="Formatar automaticamente" reason="Editor integrado indisponível." /></Row><Row title="Ditado" description="Disponibilidade de microfone e transcrição é tratada separadamente."><LinkButton to="voice" onNavigate={onNavigate}>Ver configurações de voz</LinkButton></Row></Section>
  </>;
}

function Notifications({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice title="Entrega de notificações não verificada">O Desktop ainda não consulta a permissão de notificações do sistema. Esta tela não afirma que a entrega está ativa nem que o sistema a bloqueou.</Notice>
    <Section title="Notificações nativas"><Row title="Ativar notificações" description="Alertas de eventos em segundo plano dependem de entrega nativa."><UnavailableSwitch label="Ativar notificações" reason="Entrega nativa indisponível." /></Row><Row title="Conclusão de tarefa" description="Avisar quando um agente concluir uma execução."><UnavailableSwitch label="Notificar conclusão de tarefa" reason="Assinatura de eventos indisponível." /></Row><Row title="Campainha do terminal" description="Avisar quando uma sessão de terminal emitir um alerta."><UnavailableSwitch label="Campainha do terminal" reason="Terminal integrado indisponível." /></Row><Row title="Som da notificação" description="Nenhum som é escolhido ou reproduzido nesta tela."><UnavailableSelect label="Som da notificação" /></Row><Row title="Silenciar enquanto a janela estiver em foco" description="A preferência só poderá ser aplicada quando houver entrega nativa."><UnavailableSwitch label="Silenciar notificações em foco" reason="Preferência não aplicada." /></Row><Row title="Testar entrega" description="Não será exibida uma confirmação simulada."><Unavailable label="Enviar notificação de teste" reason="Teste nativo não disponível." /></Row></Section>
    <LinkButton to="activity" onNavigate={onNavigate}>Consultar atividade no app</LinkButton>
  </>;
}

function Hosts({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Hosts SSH" action={<Unavailable label="Adicionar host SSH" reason="Conexão remota indisponível." />}><div className="ref-empty"><Glyph name="monitor" size={29} /><h3>Inventário remoto não disponível</h3><p>O Desktop não lê chaves SSH, não importa sua configuração e não abre conexões nesta tela.</p></div></Section>
    <Section title="Identidade e acesso"><Row title="Autenticação" icon="lock" description="Chaves privadas devem permanecer no mecanismo de autenticação do host. Não há campo de senha ou chave aqui."><Badge>Sem coleta de credenciais</Badge></Row><Row title="Verificação do host" description="Uma futura conexão precisa verificar identidade do servidor e obter consentimento antes de executar ações."><Unavailable label="Testar conexão SSH" reason="Transporte SSH não exposto." /></Row><Row title="Workspaces remotos" description="Um projeto local não é convertido automaticamente em workspace remoto."><LinkButton to="home" onNavigate={onNavigate}>Ver projetos locais</LinkButton></Row></Section>
  </>;
}

function Servers({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Runtime deste computador"><div className="ref-status-banner ref-status-banner-inner"><Glyph name="monitor" size={25} /><div><h3>Simplicio Runtime</h3><p>{evidence.runtimeVersion} · {evidence.transport}</p></div><Badge>{evidence.runtimeState}</Badge></div><Row title="Conexões MCP" description="Clientes locais, registro e handshake são apresentados separadamente."><LinkButton to="providers" onNavigate={onNavigate}>Ver clientes MCP</LinkButton></Row></Section>
    <Section title="Servidores remotos" description="Nenhum endereço, sessão ou autenticação de servidor remoto foi consultado."><Row title="Adicionar servidor Simplicio" description="Exige descoberta, identidade, transporte autenticado e verificação de compatibilidade."><Unavailable label="Adicionar servidor" reason="Contrato remoto indisponível." /></Row><Row title="Credenciais por servidor" description="Não são herdadas da conta Simplicio nem copiadas dos agentes."><Badge>Não coletadas</Badge></Row><Row title="Conexões SSH" description="Hosts e credenciais permanecem separados do Runtime local."><LinkButton to="hosts" onNavigate={onNavigate}>Ver hosts SSH</LinkButton></Row></Section>
  </>;
}

const permissionRows = [
  ["Microfone", "Áudio, ditado e transcrição.", "Solicitar microfone"],
  ["Câmera", "Captura de imagem e dispositivos de vídeo.", "Solicitar câmera"],
  ["Gravação de tela", "Capturas de janelas e inspeção visual.", "Revisar gravação de tela"],
  ["Acessibilidade", "Inspeção e operação de interfaces.", "Revisar acessibilidade"],
  ["Acesso a arquivos e disco", "Leitura de pastas além do contexto selecionado.", "Revisar acesso a arquivos"],
  ["Automação", "Interação entre aplicativos e eventos do sistema.", "Revisar automação"],
  ["Rede local", "Conexão a serviços e dispositivos na rede.", "Revisar rede local"],
  ["USB e Bluetooth", "Dispositivos físicos e ferramentas de desenvolvimento.", "Revisar dispositivos"],
] as const;

function Permissions({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice title="Permissões pertencem ao sistema operacional">O snapshot atual não contém uma consulta nativa de permissões. “Não consultada” não significa permissão negada nem concedida. Abrir esta página não solicita acessos.</Notice>
    <Section title="Acesso deste aplicativo"><div className="ref-permission-list">{permissionRows.map(([name, description, action]) => <Row key={name} title={name} description={description} icon="shield"><Badge>Não consultada</Badge><Unavailable label={action} reason="Consulta e abertura nativa indisponíveis." /></Row>)}</div></Section>
    <details className="ref-help-details"><summary>Como revisar manualmente</summary><p>No macOS, revise Privacidade e Segurança nos Ajustes do Sistema. No Windows, consulte Privacidade e segurança nas Configurações. No Linux, verifique as permissões do ambiente gráfico e do empacotamento utilizado. Conceda somente os acessos necessários à ação desejada.</p></details>
    <LinkButton to="computer-use" onNavigate={onNavigate}>Voltar ao uso do computador</LinkButton>
  </>;
}

function Privacy({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Section title="Dados visíveis nestas configurações"><Row title="Credenciais e contas" icon="lock" description="Esta tela não solicita tokens, cookies, senhas nem chaves privadas."><Badge>Sem campos de segredo</Badge></Row><Row title="Contexto do Runtime" description="São apresentados estados e metadados limitados. Prompts, corpos de arquivos e configurações não são exportados aqui."><Badge>Somente metadados</Badge></Row><Row title="Projetos e preferências visuais" description="Atalhos de pastas e preferências existentes ficam no armazenamento local do Desktop."><LinkButton to="general" onNavigate={onNavigate}>Ver preferências locais</LinkButton></Row></Section>
    <Section title="Telemetria"><Row title="Telemetria do Runtime" description="O snapshot desta versão não informa uma política configurável de telemetria. Não é possível inferir o estado do Runtime a partir desta tela."><Badge>Estado não informado</Badge></Row><Row title="Alterar envio de telemetria" description="Uma configuração sem efeito não será salva."><UnavailableSwitch label="Alterar envio de telemetria" reason="Contrato de configuração indisponível." /></Row></Section>
    <Section title="Compartilhamento e exportação"><Row title="Exportar diagnósticos" description="A exportação precisa de revisão e redação dos dados antes de qualquer envio."><LinkButton to="diagnostics" onNavigate={onNavigate}>Revisar diagnósticos</LinkButton></Row><Row title="Apagar todos os dados" description="Nenhum cache, credencial ou arquivo do usuário é removido por estas configurações."><Unavailable label="Apagar dados" reason="Não há exclusão em massa neste painel." /></Row></Section>
  </>;
}

function Advanced({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  return <>
    <Section title="Compatibilidade"><Row title="Runtime informado" description={evidence.runtimeVersion + " · " + evidence.transport}><LinkButton to="diagnostics" onNavigate={onNavigate}>Abrir diagnóstico</LinkButton></Row><Row title="Compatibilidade HTTP/1.1" description="O protocolo de rede não é alterado por uma preferência sem contrato nativo."><UnavailableSwitch label="Compatibilidade HTTP/1.1" reason="Configuração de transporte indisponível." /></Row></Section>
    <Section title="Rede"><Row title="Proxy HTTP" description="Nenhum proxy ou variável de ambiente é lido ou salvo aqui."><Badge>Não consultado</Badge></Row><details className="ref-help-details ref-help-inset"><summary>Configuração de proxy</summary><p>Um proxy pode conter credenciais e mudar o destino do tráfego. O Desktop ainda não oferece um plano validado para essa mudança, por isso não coleta um endereço ou senha.</p><Unavailable label="Salvar proxy" reason="Aplicação de proxy não disponível." /></details></Section>
    <Section title="Consulta segura"><CommandCard id="version" /><CommandCard id="plan" /></Section>
  </>;
}

function Experimental({ onNavigate }: { onNavigate: Navigate }) {
  return <>
    <Notice title="Experimental não significa habilitado">As superfícies abaixo dependem de contratos específicos. Nenhum recurso é ativado por visitar esta página e nenhum consentimento é ampliado.</Notice>
    <div className="ref-feature-grid">{[
      { title: "Plugins", description: "Catálogo de pacotes e limites de instalação por cliente.", icon: "apps", to: "plugins" },
      { title: "Simplicio Mobile", description: "Pareamento, dispositivos e autenticação de transporte.", icon: "monitor", to: "mobile" },
      { title: "Compartilhar skills", description: "Inventário e compartilhamento com revisão explícita.", icon: "spark", to: "share-skills" },
      { title: "Emulador mobile", description: "Dispositivos de desenvolvimento e consultas nativas.", icon: "monitor", to: "emulator" },
    ].map((feature) => <article className="ref-feature-card" key={feature.to}><Glyph name={feature.icon as GlyphName} size={23} /><h2>{feature.title}</h2><p>{feature.description}</p><button type="button" className="text-button" onClick={() => onNavigate(feature.to as View)}>Ver disponibilidade<Glyph name="arrow" size={16} /></button></article>)}</div>
  </>;
}

const pluginPackages = [
  { id: "simplicio", name: "Simplicio", description: "Runtime, MCP, ferramentas e skills para agentes compatíveis.", category: "Runtime e MCP" },
  { id: "simplicio-loop", name: "Simplicio Loop", description: "Fluxos de tarefas e orquestração governada.", category: "Orquestração" },
  { id: "simplicio-prompt", name: "Simplicio Prompt", description: "Preparação de contexto e contratos de prompt.", category: "Contexto" },
  { id: "simplicio-sprint", name: "Simplicio Sprint", description: "Compatibilidade com fluxos de sprint do ecossistema.", category: "Fluxos" },
  { id: "simplicio-hermes", name: "Simplicio Hermes", description: "Pacote de integração nativa com Hermes.", category: "Integrações" },
];

function Plugins({ evidence, onNavigate }: { evidence: Evidence; onNavigate: Navigate }) {
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<"catalog" | "reported">("catalog");
  const packages = pluginPackages.filter((plugin) => searchMatches(plugin.name + " " + plugin.description + " " + plugin.category, query));
  const skills = evidence.skills.filter((skill) => searchMatches(skill, query));
  return <>
    <Notice title="Pacote instalado e MCP registrado são estados diferentes">O reparo de integrações configura MCP e hooks. Ele não comprova a instalação, atualização ou ativação de cada pacote nativo no seu agente ou IDE.</Notice>
    <Section title="Pacotes e inventário" description="O catálogo público não é uma lista de pacotes instalados nesta máquina.">
      <div className="ref-plugin-toolbar"><div className="segmented-control" role="group" aria-label="Origem do inventário de plugins"><button type="button" aria-pressed={tab === "catalog"} className={tab === "catalog" ? "active" : ""} onClick={() => setTab("catalog")}>Catálogo público</button><button type="button" aria-pressed={tab === "reported"} className={tab === "reported" ? "active" : ""} onClick={() => setTab("reported")}>Skills informadas</button></div><label className="ref-search"><Glyph name="search" size={17} /><input aria-label="Buscar plugins e skills" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar pacote ou categoria" maxLength={120} /></label></div>
      {tab === "catalog" ? <div className="ref-plugin-grid">{packages.map((plugin) => <article className="ref-plugin-card" key={plugin.id}><div className="ref-plugin-title"><span className="ref-monogram"><Glyph name="apps" size={22} /></span><div><h3>{plugin.name}</h3><span>Ecossistema Simplicio</span></div></div><p>{plugin.description}</p><div className="ref-plugin-tags"><Badge>{plugin.category}</Badge><Badge>Instalação não verificada</Badge></div><Unavailable label={"Instalar " + plugin.name} reason="Falta um plano nativo por cliente." /></article>)}</div> : <div className="ref-reported-skills">{skills.map((skill, index) => <Row key={index} title={skill} icon="spark" description="Nome informado pelo Agent Plane; não comprova instalação do pacote."><Badge>Somente leitura</Badge></Row>)}</div>}
      {!(tab === "catalog" ? packages.length : skills.length) && <div className="ref-empty"><Glyph name="search" size={24} /><h3>{query ? "Nenhum resultado neste filtro" : "Nenhuma skill informada nesta consulta"}</h3><p>{query ? "Tente outro nome ou categoria." : "O Desktop não preenche o inventário com pacotes de demonstração."}</p>{query && <button className="button button-secondary" type="button" onClick={() => setQuery("")}>Limpar busca</button>}</div>}
    </Section>
    <Section title="Instalação e verificação"><Row title="Configurar clientes MCP" description="Abra o plano existente, revise os alvos e confirme antes de aplicar."><LinkButton to="providers" onNavigate={onNavigate}>Revisar plano MCP</LinkButton></Row><CommandCard id="plugins" /></Section>
    <details className="ref-help-details"><summary>Fontes e desenvolvimento</summary><p>Os pacotes são documentados no repositório público wesleysimplicio/simplicio. O instalador de terminal tenta instalar pacotes nos hosts detectados; isso é mais amplo que o reparo MCP. Nenhuma fonte, credencial ou pacote é adicionado ao abrir este painel.</p></details>
  </>;
}

function Body({ view, evidence, onNavigate }: { view: ReferenceSettingsView; evidence: Evidence; onNavigate: Navigate }): ReactNode {
  switch (view) {
    case "provider-accounts": return <Accounts evidence={evidence} onNavigate={onNavigate} />;
    case "orchestration": return <Orchestration evidence={evidence} onNavigate={onNavigate} />;
    case "computer-use": return <Computer evidence={evidence} onNavigate={onNavigate} />;
    case "voice": return <Voice onNavigate={onNavigate} />;
    case "general-settings": return <General evidence={evidence} onNavigate={onNavigate} />;
    case "integrations": return <Integrations onNavigate={onNavigate} />;
    case "mobile": return <Mobile onNavigate={onNavigate} />;
    case "artifacts": return <Artifacts evidence={evidence} onNavigate={onNavigate} />;
    case "share-skills": return <Skills evidence={evidence} onNavigate={onNavigate} />;
    case "git": return <Git onNavigate={onNavigate} />;
    case "task-sources": return <TaskSources onNavigate={onNavigate} />;
    case "terminal": return <Terminal onNavigate={onNavigate} />;
    case "quick-commands": return <QuickCommands />;
    case "browser": return <Browser onNavigate={onNavigate} />;
    case "emulator": return <Emulator onNavigate={onNavigate} />;
    case "floating": return <Floating onNavigate={onNavigate} />;
    case "input": return <Input onNavigate={onNavigate} />;
    case "notifications": return <Notifications onNavigate={onNavigate} />;
    case "hosts": return <Hosts onNavigate={onNavigate} />;
    case "servers": return <Servers evidence={evidence} onNavigate={onNavigate} />;
    case "permissions": return <Permissions onNavigate={onNavigate} />;
    case "privacy": return <Privacy onNavigate={onNavigate} />;
    case "advanced": return <Advanced evidence={evidence} onNavigate={onNavigate} />;
    case "experimental": return <Experimental onNavigate={onNavigate} />;
    case "plugins": return <Plugins evidence={evidence} onNavigate={onNavigate} />;
  }
}

export function ReferenceSettingsScreen({ view, snapshot, onNavigate, onRefresh, busy = false }: ReferenceSettingsProps) {
  const screen = REFERENCE_SCREENS.find((item) => item.id === view)!;
  const evidence = createReferenceSettingsEvidence(snapshot);
  return <div className="page reference-settings-page" data-settings-view={view}>
    <header className="ref-page-heading"><div><span className="ref-eyebrow">{screen.group}</span><h1>{screen.label}</h1><p>{screen.description}</p></div>{onRefresh && <button type="button" className="button button-secondary" onClick={onRefresh} disabled={busy} aria-label="Atualizar consulta do Runtime"><Glyph name="refresh" size={16} />{busy ? "Consultando…" : "Atualizar consulta"}</button>}</header>
    {snapshot.source === "preview" && <div className="ref-preview-note" role="note"><Glyph name="attention" size={17} /><span>Prévia visual. Instalação, contas, permissões e conexões deste computador não foram verificadas.</span></div>}
    <Body key={view} view={view} evidence={evidence} onNavigate={onNavigate} />
    <footer className="ref-evidence-footer"><Glyph name="lock" size={15} /><p>{evidence.source === "runtime" ? "Metadados da consulta ao Runtime: " + evidence.observedAt + ". Abrir esta tela não renova a consulta nem autoriza ações." : "Nenhum estado da prévia é usado como comprovação de conexão ou instalação."}</p></footer>
  </div>;
}
