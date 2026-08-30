import type { BotCenterSnapshot, DesktopSnapshot } from "../contracts";
import type { View } from "../components/Shell";
import { Glyph } from "../components/Brand";
import { createTodayProjection } from "../today_projection";
import { createAmbientProjection } from "../ambient";
import { createChatProjection } from "../chat_projection";
import { createCapabilityRegistry } from "../capability_registry";
import { createAutomationProjection } from "../automation_projection";
import { createWorkspaceProjection } from "../workspace_projection";
import { createMultiChatProjection } from "../multi_chat_projection";
import { createWorkItemProjection } from "../work_item_projection";
import { createLiveProjection } from "../live_projection";
import { createRoomProjection } from "../room_projection";

type ProductView = Extract<View, "today" | "chats" | "teams" | "automations" | "apps">;

const surfaceCopy: Record<ProductView, { eyebrow: string; title: string; description: string }> = {
  today: { eyebrow: "Visão geral", title: "Today", description: "Uma fila calma do que merece sua atenção agora." },
  chats: { eyebrow: "Conversas", title: "Chats", description: "Sessões, ferramentas e entregas ligadas ao mesmo Runtime." },
  teams: { eyebrow: "Colaboração", title: "Teams", description: "Pessoas, Bots, Rooms e Work Items no mesmo espaço." },
  automations: { eyebrow: "Fluxos", title: "Automations", description: "Sugestões e rotinas com aprovação explícita." },
  apps: { eyebrow: "Capacidades", title: "Apps", description: "Ferramentas disponíveis, artefatos e relatórios de uso." },
};

function SurfaceHeading({ view, snapshot }: { view: ProductView; snapshot: DesktopSnapshot }) {
  const copy = surfaceCopy[view];
  return (
    <section className="page-heading product-heading">
      <div>
        <span className="eyebrow">{copy.eyebrow}</span>
        <h1>{copy.title}</h1>
        <p>{copy.description}</p>
      </div>
      <span className={`projection-badge ${snapshot.source === "preview" ? "preview" : "live"}`}>
        <span className="status-dot" /> {snapshot.source === "preview" ? "Projeção de demonstração" : "Projeção do Runtime"}
      </span>
    </section>
  );
}

function UnavailableNotice({ code, children }: { code: string; children: string }) {
  return (
    <div className="projection-notice" role="status">
      <Glyph name="shield" size={18} />
      <div><strong>Contrato aguardando o Runtime</strong><p>{children}</p><code>reason: {code}</code></div>
    </div>
  );
}

function ActionButton({ children, title = "Ação bloqueada até o Runtime confirmar a capability" }: { children: string; title?: string }) {
  return <button className="button button-secondary" type="button" disabled title={title}>{children}</button>;
}

function TodayScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const projection = createTodayProjection(snapshot);
  const ambient = createAmbientProjection(snapshot);
  const { focus, inProgress, upNext } = projection;
  return (
    <div className="page product-page">
      <SurfaceHeading view="today" snapshot={snapshot} />
      <UnavailableNotice code="ambient.today_projection_unavailable">
        A fila abaixo é somente a projeção instalada; o Runtime ainda não expôs o contrato `ambient.today/v1`.
      </UnavailableNotice>
      <section className="today-grid">
        <article className="panel today-focus">
          <div className="panel-heading"><div><span className="eyebrow">Agora</span><h2>Focus</h2></div><span className="attention-chip">1 item</span></div>
          {focus ? <div className="focus-card"><span className="focus-icon"><Glyph name="spark" size={20} /></span><div><strong>{focus.title}</strong><p>{focus.detail}</p><span>{focus.provider} · recibo {focus.status === "verified" ? "verificado" : "pendente"}</span></div><ActionButton>Continuar</ActionButton></div> : <p className="empty-state">Nenhum foco foi projetado.</p>}
          <div className="focus-footer"><span>Uma decisão por vez</span><ActionButton>Trocar foco</ActionButton></div>
        </article>
        <aside className="today-side panel">
          <div className="panel-heading"><div><span className="eyebrow">Ambiente</span><h2>Estado</h2></div><span className={`healthy-badge ${ambient.state === "attention" ? "warning" : ""}`}><span className={`status-dot ${ambient.state === "quiet" ? "online" : ambient.state === "unavailable" ? "offline" : "warning"}`} /> {ambient.state}</span></div>
          <div className="ambient-orbit"><span /><span /><span /><Glyph name="spark" size={18} /></div>
          <p>O estado visual permanece quieto até existir um evento novo, atenção ou sessão Live.</p>
          <dl className="compact-facts"><div><dt>Workspace</dt><dd>Personal</dd></div><div><dt>Runtime</dt><dd>{snapshot.runtime.transport}</dd></div><div><dt>Último recibo</dt><dd>{snapshot.runtime.lastReceiptAt ?? "—"}</dd></div></dl>
        </aside>
      </section>
      <section className="today-columns">
        <article className="panel queue-panel"><div className="panel-heading"><div><span className="eyebrow">Fila curta</span><h2>In Progress</h2></div><span className="queue-count">{inProgress.length}/3</span></div>{inProgress.length ? inProgress.map((item) => <QueueRow key={item.id} title={item.title} detail={item.provider} status="running" />) : <p className="empty-state">Nada em andamento.</p>}</article>
        <article className="panel queue-panel"><div className="panel-heading"><div><span className="eyebrow">Depois</span><h2>Up Next</h2></div><span className="queue-count">{upNext.length}/3</span></div>{upNext.length ? upNext.map((item) => <QueueRow key={item.id} title={item.title} detail={item.provider} status={item.status} />) : <p className="empty-state">Nenhuma próxima ação.</p>}</article>
      </section>
    </div>
  );
}

function QueueRow({ title, detail, status }: { title: string; detail: string; status: string }) {
  return <div className="queue-row"><span className={`queue-dot ${status === "running" ? "running" : "ready"}`} /><div><strong>{title}</strong><span>{detail} · {status === "running" ? "em andamento" : "pronto"}</span></div><Glyph name="chevron" size={14} /></div>;
}

function ChatsScreen({ snapshot, botCenter }: { snapshot: DesktopSnapshot; botCenter: BotCenterSnapshot }) {
  const projection = createChatProjection(botCenter);
  const workspace = createMultiChatProjection(botCenter);
  const session = botCenter.sessions[0];
  const events = projection.events;
  return (
    <div className="page product-page">
      <SurfaceHeading view="chats" snapshot={snapshot} />
      <div className="chat-layout">
        <aside className="panel session-list"><div className="panel-heading"><div><span className="eyebrow">Sessões</span><h2>Chats</h2></div><span className="queue-count">{workspace.sessions.length}</span></div>{workspace.sessions.map((chat) => <button className={`session-card ${workspace.selectedSessionId === chat.sessionId ? "active" : ""}`} type="button" key={chat.sessionId}><span className="bot-avatar">{chat.title.slice(0, 1).toUpperCase()}</span><span><strong>{chat.title}</strong><small>{chat.state} · rev. {chat.revision} · {chat.unread} eventos</small></span></button>)}<ActionButton title="Criar sessão exige o Agent API do Runtime">+ Novo chat</ActionButton></aside>
        <section className="panel chat-session"><div className="chat-session-head"><div><span className="eyebrow">Session Service</span><h2>Cora <small>· {projection.sessionId ?? "sem sessão"}</small></h2></div><div className="chat-head-actions"><ActionButton>Steer</ActionButton><ActionButton>Cancelar</ActionButton></div></div>
          <UnavailableNotice code={projection.reasonCode}>O histórico é redigido e limitado; streaming, approvals e envio dependem do contrato canônico do Runtime.</UnavailableNotice>
          <div className="chat-events">{events.filter((event) => event.kind === "message" || event.kind === "tool_result" || event.kind === "approval_request" || event.kind === "artifact").map((event) => <article className={`chat-event ${event.actorKind} ${event.state === "blocked" ? "blocked" : ""}`} key={event.eventId}><span className="chat-event-avatar">{event.actorKind === "human" ? "V" : event.actorKind === "bot" ? "C" : "R"}</span><div><div className="chat-event-meta"><strong>{event.actorLabel}</strong><span>{event.kind.replaceAll("_", " ")}</span></div><p>{event.content}</p>{event.toolName && <code>tool: {event.toolName}</code>}{event.approvalId && <code>approval: {event.approvalId}</code>}{event.artifactName && <button className="inline-link" type="button" disabled>{event.artifactName}</button>}</div></article>)}</div>
          <div className="chat-composer"><textarea aria-label="Mensagem do chat" placeholder="Escreva uma mensagem…" disabled /><div><span>Enviar cria um evento no Runtime e requer sessão ativa.</span><ActionButton>Enviar</ActionButton></div></div>
        </section>
      </div>
    </div>
  );
}

function TeamsScreen({ snapshot, botCenter }: { snapshot: DesktopSnapshot; botCenter: BotCenterSnapshot }) {
  const workspace = createWorkspaceProjection(snapshot, botCenter);
  const space = workspace.spaces[0];
  const team = workspace.teams[0];
  const room = botCenter.rooms.find((candidate) => team?.roomIds.includes(candidate.roomId));
  const workItem = createWorkItemProjection(snapshot, botCenter);
  const live = createLiveProjection(snapshot, botCenter);
  const roomProjection = createRoomProjection(snapshot, botCenter);
  return (
    <div className="page product-page">
      <SurfaceHeading view="teams" snapshot={snapshot} />
      <div className="workspace-layout">
        <section className="panel teams-panel"><div className="panel-heading"><div><span className="eyebrow">Spaces</span><h2>Teams</h2></div><ActionButton>Criar Team</ActionButton></div><div className="space-card active"><span className="space-avatar">P</span><div><strong>{space?.displayName ?? "Personal"}</strong><span>Workspace padrão · {team?.memberIds.length ?? 0} membros projetados</span></div><span className="space-state">{space?.active ? "ativo" : "inativo"}</span></div><div className="space-card"><span className="space-avatar muted">+</span><div><strong>Novo Space</strong><span>Disponível quando o Workspace API estiver pronto</span></div></div><div className="team-subsection"><span className="eyebrow">Team Rooms</span>{room ? <div className="room-row"><span className="room-icon"><Glyph name="teams" size={16} /></span><div><strong>{roomProjection.displayName}</strong><span>{roomProjection.members.join(" · ")}</span><div className="room-modes">{roomProjection.modes.map((mode) => <button className={roomProjection.activeMode === mode ? "active" : ""} key={mode} type="button" disabled={!roomProjection.modeChangeAvailable}>{mode}</button>)}</div></div><span className="room-unread">{room.unread}</span></div> : <p className="empty-state">Nenhuma Room projetada.</p>}</div></section>
        <section className="panel work-item-panel"><div className="panel-heading"><div><span className="eyebrow">Work Items</span><h2>Mission Control</h2></div><span className="attention-chip">{workItem.status === "blocked" ? "1 atenção" : workItem.status}</span></div><article className="work-item-card"><div className="work-item-title"><span className={`work-item-status ${workItem.status === "blocked" ? "blocked" : "running"}`} /><div><strong>{workItem.title}</strong><span>{workItem.workItemId} · {workItem.botId ?? "sem Bot"} · {room?.displayName ?? "sem Room"}</span></div></div><p>{workItem.status === "blocked" ? "O item está aguardando aprovação e não será iniciado automaticamente." : "Estado projetado pelo Runtime."}</p><div className="work-item-footer"><span>{workItem.status} · {workItem.approvalId ?? workItem.reasonCode}</span><ActionButton>Assumir</ActionButton></div></article>{live.visible ? <div className="live-dock"><div><span className="eyebrow">Live Dock</span><strong>{live.tasks.length} sessão(ões) com atenção</strong></div><Glyph name="live" size={22} /></div> : <div className="live-dock is-hidden"><div><span className="eyebrow">Live Dock</span><strong>Oculto até existir trabalho ativo</strong></div><Glyph name="live" size={22} /></div>}</section>
      </div>
      <UnavailableNotice code={workspace.reasonCode}>Membership, reassign, threads e criação de Work Items precisam do Workspace/Session Service do Runtime.</UnavailableNotice>
    </div>
  );
}

function AutomationsScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const projection = createAutomationProjection(snapshot);
  const suggestions = projection.suggestions;
  return (
    <div className="page product-page">
      <SurfaceHeading view="automations" snapshot={snapshot} />
      <div className="automation-layout"><section className="panel suggestion-panel"><div className="panel-heading"><div><span className="eyebrow">Inbox</span><h2>Sugestões</h2></div><span className="queue-count">{suggestions.length}</span></div>{suggestions.length ? suggestions.map((item) => <article className="suggestion-card" key={item.id}><span className="suggestion-icon"><Glyph name="spark" size={17} /></span><div><strong>{item.title}</strong><p>{item.description}</p><span>receipt: {item.sourceEventId} · {item.state}</span></div><div className="suggestion-actions"><ActionButton>Aceitar</ActionButton><ActionButton>Descartar</ActionButton></div></article>) : <p className="empty-state">Nenhuma sugestão disponível.</p>}</section><section className="panel studio-panel"><div className="panel-heading"><div><span className="eyebrow">Studio</span><h2>Nova automação</h2></div><Glyph name="automation" size={18} /></div><div className="studio-step"><span>1</span><div><strong>Quando</strong><p>Escolha um evento do Runtime ou uma rotina.</p></div></div><div className="studio-step"><span>2</span><div><strong>Fazer</strong><p>Selecione uma capability e sua política.</p></div></div><div className="studio-step"><span>3</span><div><strong>Revisar</strong><p>Salvar cria apenas um rascunho versionado.</p></div></div><ActionButton>Salvar rascunho</ActionButton></section></div>
      <section className="panel automation-receipts"><div className="panel-heading"><div><span className="eyebrow">Activity Center</span><h2>Recibos recentes</h2></div><ActionButton>Exportar</ActionButton></div><div className="receipt-strip"><span><strong>{snapshot.activity.length}</strong> eventos limitados</span><span><strong>—</strong> automações ativas</span><span><strong>—</strong> ações aguardando você</span></div></section>
      <UnavailableNotice code={projection.reasonCode}>Triggers, budgets, quiet hours, cancelamento e políticas são autoridade do Runtime; a UI fica sem efeito até a capability ser verificada.</UnavailableNotice>
    </div>
  );
}

function AppsScreen({ snapshot }: { snapshot: DesktopSnapshot }) {
  const registry = createCapabilityRegistry(snapshot);
  const apps = registry.capabilities;
  return (
    <div className="page product-page"><SurfaceHeading view="apps" snapshot={snapshot} /><div className="apps-toolbar"><div className="search-field"><Glyph name="search" size={16} /><span>Buscar capabilities, artifacts ou comandos</span><kbd>⌘K</kbd></div><ActionButton>Favoritos</ActionButton></div><section className="app-grid">{apps.map((app) => <article className="panel app-card" key={app.id}><div className="app-card-head"><span className="app-icon"><Glyph name={app.category === "Learn" ? "spark" : app.category === "Explore" ? "search" : app.category === "Act" ? "live" : app.category === "Build" ? "providers" : "apps"} size={19} /></span><span className="app-category">{app.category}</span></div><h2>{app.name}</h2><p>{app.description}</p><code>{app.reasonCode}</code><ActionButton>Abrir</ActionButton></article>)}</section><div className="apps-bottom-grid"><section className="panel library-card"><div className="panel-heading"><div><span className="eyebrow">Artifact Graph</span><h2>Library</h2></div><ActionButton>Ver tudo</ActionButton></div><p>Artifacts, versões e proveniência aparecem quando o Runtime fornecer handles canônicos.</p><div className="library-row"><span className="file-icon">MD</span><div><strong>desktop-bot-mode-plan.md</strong><span>preview · sem cópia local</span></div></div></section><section className="panel token-card"><div className="panel-heading"><div><span className="eyebrow">Receipts</span><h2>Token Reports</h2></div><Glyph name="activity" size={18} /></div><strong className="report-value">—</strong><p>Sem métrica agregada verificável para este período.</p><code>proof: unavailable</code></section></div><UnavailableNotice code={registry.reasonCode}>Apps só ficam acionáveis depois de um probe do backend; o launcher não presume capacidades instaladas.</UnavailableNotice></div>
  );
}

export function ProductSurfaceScreen({ view, snapshot, botCenter }: { view: ProductView; snapshot: DesktopSnapshot; botCenter: BotCenterSnapshot }) {
  if (view === "today") return <TodayScreen snapshot={snapshot} />;
  if (view === "chats") return <ChatsScreen snapshot={snapshot} botCenter={botCenter} />;
  if (view === "teams") return <TeamsScreen snapshot={snapshot} botCenter={botCenter} />;
  if (view === "automations") return <AutomationsScreen snapshot={snapshot} />;
  return <AppsScreen snapshot={snapshot} />;
}
