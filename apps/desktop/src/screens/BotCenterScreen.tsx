import { FormEvent, useMemo, useRef, useState } from "react";
import type {
  BotActionKind,
  BotCenterSnapshot,
  BotLifecycle,
  BotSessionProjection,
  BotTimelineEvent,
} from "../contracts";
import type { BotActionRequest } from "../bot_center";
import { Glyph } from "../components/Brand";

const lifecycleLabel: Record<BotLifecycle, string> = {
  disabled: "desabilitado",
  idle: "ocioso",
  active: "ativo",
  busy: "ocupado",
  degraded: "degradado",
  blocked: "bloqueado",
};

const eventLabel: Record<BotTimelineEvent["kind"], string> = {
  message: "mensagem",
  tool_call: "tool call",
  tool_result: "resultado",
  approval_request: "aprovação",
  approval_decision: "decisão",
  artifact: "artifact",
  attachment: "anexo",
  status: "status",
  bot_event: "bot-to-bot",
};

function sessionFor(snapshot: BotCenterSnapshot, botId: string): BotSessionProjection | undefined {
  const bot = snapshot.bots.find((item) => item.botId === botId);
  return snapshot.sessions.find((session) => session.sessionId === bot?.lastSessionId)
    ?? snapshot.sessions.find((session) => session.botId === botId);
}

function formatNumber(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("pt-BR");
}

function statusClass(lifecycle: BotLifecycle): string {
  return lifecycle === "active" || lifecycle === "busy" ? "bot-status-live" : lifecycle === "blocked" ? "bot-status-blocked" : "bot-status-muted";
}

/** Synchronous admission also covers repeated clicks before React renders busy state. */
export async function dispatchAvailableBotAction({ request, authority, pending, onAction, onBusy }: {
  request: BotActionRequest;
  authority: BotCenterSnapshot["actionAuthority"];
  pending: { current: boolean };
  onAction: (request: BotActionRequest) => Promise<void>;
  onBusy: (action: BotActionKind | null) => void;
}): Promise<void> {
  if ((authority !== "runtime" && authority !== "preview") || pending.current) return;
  pending.current = true;
  try {
    onBusy(request.kind);
    await onAction(request);
  } finally {
    pending.current = false;
    onBusy(null);
  }
}

function TimelineEvent({ item, onAction, disabled }: { item: BotTimelineEvent; onAction: (request: BotActionRequest) => Promise<void>; disabled: boolean }) {
  const approvalAction: BotActionKind | null = item.kind === "approval_request" && item.approvalId ? "approve" : null;
  return (
    <article className={`bot-event bot-event-${item.kind} ${item.state === "blocked" ? "is-blocked" : ""}`}>
      <div className="bot-event-marker"><Glyph name={item.kind === "tool_call" || item.kind === "tool_result" ? "settings" : item.kind === "approval_request" ? "shield" : item.kind === "bot_event" ? "spark" : "activity"} size={15} /></div>
      <div className="bot-event-body">
        <div className="bot-event-meta">
          <strong>{item.actorLabel}</strong>
          <span>{eventLabel[item.kind]}</span>
          <time dateTime={item.timestamp}>{new Date(item.timestamp).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</time>
        </div>
        <p>{item.content}</p>
        {item.toolName && <code className="bot-tool-name">{item.toolName}</code>}
        {item.artifactName && <button className="bot-inline-link" type="button" disabled title="Abertura de artifacts aguardando action descriptor do Runtime">Abrir {item.artifactName}</button>}
        {item.attachmentName && <span className="bot-attachment-chip"><Glyph name="check" size={13} /> {item.attachmentName}</span>}
        {item.reasonCode && <span className="bot-reason">reason: {item.reasonCode}</span>}
        {approvalAction && (
          <div className="bot-approval-actions">
            <button className="button button-primary" type="button" disabled={disabled} onClick={() => onAction({ kind: "approve", botId: item.botId, sessionId: item.sessionId, approvalId: item.approvalId })}>Aprovar</button>
            <button className="button button-secondary" type="button" disabled={disabled} onClick={() => onAction({ kind: "deny", botId: item.botId, sessionId: item.sessionId, approvalId: item.approvalId })}>Negar</button>
          </div>
        )}
      </div>
    </article>
  );
}

export function BotCenterScreen({ snapshot, onAction }: { snapshot: BotCenterSnapshot; onAction: (request: BotActionRequest) => Promise<void> }) {
  const [selectedBotId, setSelectedBotId] = useState(snapshot.selectedBotId ?? snapshot.bots[0]?.botId ?? null);
  const [message, setMessage] = useState("");
  const [steer, setSteer] = useState("");
  const [busyAction, setBusyAction] = useState<BotActionKind | null>(null);
  const actionLock = useRef(false);
  const selectedBot = snapshot.bots.find((bot) => bot.botId === selectedBotId) ?? null;
  const session = selectedBotId ? sessionFor(snapshot, selectedBotId) : undefined;
  const room = snapshot.rooms.find((item) => item.sessionId === session?.sessionId) ?? snapshot.rooms[0];
  const recentEvents = useMemo(() => session?.events.slice(-30) ?? [], [session]);
  const isUnavailable = snapshot.actionAuthority !== "runtime" && snapshot.actionAuthority !== "preview";

  async function dispatch(request: BotActionRequest) {
    await dispatchAvailableBotAction({ request, authority: snapshot.actionAuthority, pending: actionLock, onAction, onBusy: setBusyAction });
  }

  async function submitTurn(event: FormEvent) {
    event.preventDefault();
    if (!selectedBotId || !message.trim() || !session) return;
    const value = message.trim();
    setMessage("");
    await dispatch({ kind: "send_turn", botId: selectedBotId, sessionId: session.sessionId, value });
  }

  async function submitSteer(event: FormEvent) {
    event.preventDefault();
    if (!selectedBotId || !session || !steer.trim()) return;
    const value = steer.trim();
    setSteer("");
    await dispatch({ kind: "steer", botId: selectedBotId, sessionId: session.sessionId, value });
  }

  const actionDisabled = isUnavailable || busyAction !== null;

  return (
    <div className="page bot-center-page">
      <section className="page-heading bot-center-heading">
        <div>
          <span className="eyebrow">Agent Plane · superfície pública</span>
          <h1>Bot Center</h1>
          <p>Roster, sessões, Rooms e Computer governados pelo Runtime.</p>
        </div>
        <div className={`bot-authority-badge ${isUnavailable ? "is-unavailable" : ""}`}>
          <span className="status-dot" />
          {isUnavailable ? "Contrato indisponível" : snapshot.source === "preview" ? "Preview" : "Runtime verificado"}
        </div>
      </section>

      {isUnavailable && (
        <section className="bot-contract-warning" role="status">
          <Glyph name="shield" size={20} />
          <div><strong>Bot Mode ainda não foi exposto pelo Runtime.</strong><p>O Desktop não cria bots nem reimplementa o Agent Plane localmente. reason: {snapshot.computer.reasonCode}</p></div>
        </section>
      )}

      <div className="bot-center-grid">
        <aside className="panel bot-roster-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Roster canônico</span><h2>Bots <small>{snapshot.bots.length}/{snapshot.limits.maxBots}</small></h2></div>
            <button className="text-button" type="button" disabled title="Criação de Bot aguardando action descriptor do Runtime" aria-label="Criar novo Bot">Novo <Glyph name="arrow" size={15} /></button>
          </div>
          <div className="bot-roster-list">
            {snapshot.bots.length === 0 ? <p className="empty-state">Nenhum Bot exposto pelo Runtime.</p> : snapshot.bots.map((bot) => (
              <button key={bot.botId} type="button" className={`bot-roster-item ${bot.botId === selectedBotId ? "active" : ""}`} onClick={() => setSelectedBotId(bot.botId)}>
                <span className="bot-avatar">{bot.displayName.slice(0, 1)}</span>
                <span className="bot-roster-copy"><strong>{bot.displayName}</strong><small>{bot.provider ?? "provider não informado"}</small></span>
                <span className={`bot-status-dot ${statusClass(bot.lifecycle)}`} title={bot.reasonCode} />
              </button>
            ))}
          </div>
          <div className="bot-roster-foot"><Glyph name="shield" size={14} /> status derivado de receipts</div>
        </aside>

        <section className="panel bot-chat-panel">
          {selectedBot ? (
            <>
              <header className="bot-chat-header">
                <div className="bot-chat-identity"><span className="bot-avatar bot-avatar-large">{selectedBot.displayName.slice(0, 1)}</span><div><h2>{selectedBot.displayName}</h2><p><span className={`bot-status-dot ${statusClass(selectedBot.lifecycle)}`} /> {lifecycleLabel[selectedBot.lifecycle]} · {selectedBot.reasonCode}</p></div></div>
                <div className="bot-chat-actions">
                  <button className="text-button" type="button" disabled={actionDisabled || !session} onClick={() => session && dispatch({ kind: "resume", botId: selectedBot.botId, sessionId: session.sessionId })}>Retomar</button>
                  <button className="text-button" type="button" disabled={actionDisabled || !session} onClick={() => session && dispatch({ kind: "branch", botId: selectedBot.botId, sessionId: session.sessionId })}>Branch</button>
                  <button className="text-button" type="button" disabled={actionDisabled || !session} onClick={() => session && dispatch({ kind: "handoff", botId: selectedBot.botId, sessionId: session.sessionId })}>Handoff</button>
                </div>
              </header>

              <div className="bot-selectors" aria-label="Configuração projetada do Bot">
                <label>Provider<select value={selectedBot.provider ?? "—"} disabled><option>{selectedBot.provider ?? "Não informado"}</option></select></label>
                <label>Modelo<select value={selectedBot.model ?? "—"} disabled><option>{selectedBot.model ?? "Não informado"}</option></select></label>
                <label>Profile<select value={selectedBot.profileId} disabled><option>{selectedBot.profileId}</option></select></label>
                <label>Projeto<select value={selectedBot.projectId ?? "—"} disabled><option>{selectedBot.projectId ?? "Não associado"}</option></select></label>
              </div>

              <div className="bot-chip-row"><span>toolset: {selectedBot.toolset.join(" · ") || "—"}</span><span>skills: {selectedBot.skills.join(" · ") || "—"}</span></div>

              <div className="bot-timeline" aria-live="polite">
                {recentEvents.length === 0 ? <p className="empty-state">Sem transcript disponível para este Bot.</p> : recentEvents.map((item) => <TimelineEvent key={item.eventId} item={item} onAction={dispatch} disabled={actionDisabled} />)}
              </div>

              <div className="bot-composer-wrap">
                <form className="bot-composer" onSubmit={submitTurn}>
                  <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Enviar um turn ao Bot…" rows={2} disabled={actionDisabled || !session} aria-label="Mensagem para o Bot" />
                  <div><span className="bot-compose-hint">session: {session?.sessionId ?? "não disponível"}</span><button className="button button-primary" type="submit" disabled={actionDisabled || !session || !message.trim()}>{busyAction === "send_turn" ? "Enviando…" : "Enviar"}<Glyph name="arrow" size={16} /></button></div>
                </form>
                <form className="bot-steer-form" onSubmit={submitSteer}><input value={steer} onChange={(event) => setSteer(event.target.value)} placeholder="Steer opcional" disabled={actionDisabled || !session} aria-label="Steer do Bot" /><button className="text-button" type="submit" disabled={actionDisabled || !session || !steer.trim()}>Steer</button></form>
                <div className="bot-quick-actions"><button className="button button-secondary" type="button" disabled={actionDisabled || !session} onClick={() => session && dispatch({ kind: "interrupt", botId: selectedBot.botId, sessionId: session.sessionId })}>Interromper</button><button className="button button-secondary" type="button" disabled={actionDisabled || !session} onClick={() => session && dispatch({ kind: "cancel", botId: selectedBot.botId, sessionId: session.sessionId })}>Cancelar</button></div>
              </div>
            </>
          ) : <div className="bot-empty-detail"><Glyph name="spark" size={28} /><h2>Escolha um Bot</h2><p>A lista é preenchida pela projeção canônica do Runtime.</p></div>}
        </section>

        <aside className="bot-side-rail">
          <section className="panel bot-room-panel">
            <div className="panel-heading"><div><span className="eyebrow">Session Service</span><h2>Rooms</h2></div><span className="room-count">{snapshot.rooms.length}</span></div>
            {snapshot.rooms.length === 0 ? <p className="empty-state">Nenhuma Room disponível.</p> : snapshot.rooms.map((item) => <article className="bot-room-card" key={item.roomId}><div><strong>{item.displayName}</strong><span>{item.members.map((member) => member.label).join(" · ")}</span></div>{item.unread > 0 && <b>{item.unread}</b>}</article>)}
            <p className="bot-side-note">Histórico, threads e membership vêm do mesmo binding de sessão.</p>
          </section>

          <section className="panel bot-computer-panel">
            <div className="panel-heading"><div><span className="eyebrow">Capability</span><h2>Computer</h2></div><span className={`computer-state ${snapshot.computer.available ? "available" : "unavailable"}`}>{snapshot.computer.available ? snapshot.computer.state : "indisponível"}</span></div>
            <div className="computer-illustration"><Glyph name="spark" size={27} /></div>
            <p>{snapshot.computer.available ? "Sessão observável vinculada ao Bot selecionado." : "Nenhum backend Computer real foi verificado; ações permanecem bloqueadas."}</p>
            <code>reason: {snapshot.computer.reasonCode}</code>
            <div className="computer-actions"><button className="button button-secondary" type="button" disabled={!snapshot.computer.available || actionDisabled || !selectedBotId} onClick={() => dispatch({ kind: "take_over", botId: selectedBotId ?? "", sessionId: session?.sessionId })}>Assumir controle</button><button className="button button-secondary" type="button" disabled={!snapshot.computer.available || actionDisabled || !selectedBotId} onClick={() => dispatch({ kind: "hand_back", botId: selectedBotId ?? "", sessionId: session?.sessionId })}>Devolver ao Bot</button></div>
          </section>

          <section className="panel bot-telemetry-panel">
            <div className="panel-heading"><div><span className="eyebrow">Receipts</span><h2>Medição</h2></div><Glyph name="activity" size={18} /></div>
            {session ? <dl className="bot-telemetry"><div><dt>Input</dt><dd>{formatNumber(session.tokenUsage.input)}</dd></div><div><dt>Output</dt><dd>{formatNumber(session.tokenUsage.output)}</dd></div><div><dt>Reasoning</dt><dd>{formatNumber(session.tokenUsage.reasoning)}</dd></div><div><dt>Cache</dt><dd>{session.cacheHitPercent === null ? "—" : `${session.cacheHitPercent.toLocaleString("pt-BR")}%`}</dd></div><div><dt>Custo</dt><dd>{session.costUsd === null ? "—" : `US$ ${session.costUsd.toFixed(4)}`}</dd></div></dl> : <p className="empty-state">Sem telemetria medida.</p>}
            <span className="bot-measurement-note">{session?.tokenUsage.proofKind === "measured" ? "medido pelo Runtime" : "sem evidência"}</span>
          </section>
        </aside>
      </div>
      {room && <p className="bot-footer-receipt">room: {room.roomId} · session: {session?.sessionId ?? "—"} · revision: {session?.revision ?? "—"} · eventos limitados a {snapshot.limits.maxEvents}</p>}
    </div>
  );
}
