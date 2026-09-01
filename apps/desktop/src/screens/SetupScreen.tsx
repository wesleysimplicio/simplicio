import { useEffect, useRef, useState } from "react";
import { planDesktopIntegrations, refreshDesktopSnapshot } from "../bridge";
import { Brand, Glyph } from "../components/Brand";
import type { DesktopSnapshot } from "../contracts";
import {
  hostPluginOutcomeLabel,
  integrationChangeLabel,
  type HostPluginOperationResult,
  type HostPluginId,
  type HostPluginResultStatus,
  type IntegrationPlan,
} from "../integration_setup";
import type { InstallFailureRecovery } from "../install_failures";
import { canConfigureRuntime, setupStages, type SetupPhase, type SetupStep } from "../setup_flow";

const HOST_LABELS: Readonly<Record<HostPluginId, string>> = {
  codex: "Codex",
  claude: "Claude Code",
  gemini: "Gemini CLI",
  copilot: "GitHub Copilot",
  qwen: "Qwen Code",
  hermes: "Hermes",
  cursor: "Cursor",
  kiro: "Kiro",
};

function resultLabel(host: { status: HostPluginResultStatus }): string {
  switch (host.status) {
    case "verified": return "Verificado";
    case "applied_unverified": return "Aplicado; verificação indisponível";
    case "not_detected": return "Não detectado";
    case "failed": return "Falhou";
    case "drifted": return "Divergente";
    case "blocked": return "Ação manual necessária";
    case "pending": return "Pendente";
    case "applying": return "Aplicando";
    case "unknown": return "Estado desconhecido";
  }
}

export function SetupScreen({ snapshot, busy, applicationError, applicationRecovery, initialOutcome, onSnapshot, onApply, onReconcile, onFinish, onDiagnostics }: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  applicationError: string | null;
  applicationRecovery?: InstallFailureRecovery;
  initialOutcome?: HostPluginOperationResult;
  onSnapshot: (snapshot: DesktopSnapshot) => void;
  onApply: (digest: string) => Promise<HostPluginOperationResult>;
  onReconcile: (receiptId: string) => Promise<HostPluginOperationResult>;
  onFinish: () => void;
  onDiagnostics: () => void;
}) {
  const [phase, setPhase] = useState<SetupPhase>("welcome");
  const [failedStep, setFailedStep] = useState<SetupStep>(1);
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [outcome, setOutcome] = useState<HostPluginOperationResult | null>(initialOutcome ?? null);
  const [confirmed, setConfirmed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [failure, setFailure] = useState("");
  const operationLock = useRef(false);
  const submittedPlanDigest = useRef<string | null>(null);
  const submittedReconcileId = useRef<string | null>(null);
  const content = useRef<HTMLElement>(null);
  const headingElement = useRef<HTMLHeadingElement>(null);
  const detailsElement = useRef<HTMLElement>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const pending = ["checking", "planning", "installing", "reconciling"].includes(phase);
  const locked = busy || pending;
  const preview = snapshot.source === "preview";
  const receipt = outcome?.snapshot;
  const projected = snapshot.hostPlugins;
  const reconcileReceiptId = (receipt && ["partial", "requires_reconcile"].includes(receipt.state) ? receipt.receiptId : null)
    ?? (!outcome && projected?.reconcileRequired ? projected.reconcileReceiptId ?? null : null);
  const runtimePending = !outcome && projected?.reconcileRequired === true;
  const blockedWithoutReceipt = Boolean((applicationRecovery && applicationRecovery !== "review" || runtimePending) && !reconcileReceiptId);
  const reconcileConsumed = Boolean(reconcileReceiptId && submittedReconcileId.current === reconcileReceiptId);
  const steps = setupStages(phase, failedStep);
  const completed = steps.filter((step) => step.state === "complete").length;
  const currentStage = steps.find((step) => step.state === "running" || step.state === "failed");

  useEffect(() => {
    content.current?.scrollTo({ top: 0 });
    if (["review", "complete", "failed"].includes(phase)) headingElement.current?.focus({ preventScroll: true });
  }, [phase]);

  useEffect(() => {
    if (showDetails) detailsElement.current?.scrollIntoView({ block: "nearest" });
  }, [showDetails]);

  async function prepare() {
    if (operationLock.current || busy || blockedWithoutReceipt || runtimePending) return;
    operationLock.current = true;
    submittedPlanDigest.current = null;
    submittedReconcileId.current = null;
    setPlan(null); setOutcome(null); setConfirmed(false); setFailure(""); setPhase("checking");
    let currentStep: SetupStep = 1;
    try {
      const next = await refreshDesktopSnapshot();
      onSnapshot(next);
      if (!canConfigureRuntime(next)) throw new Error("runtime_not_ready");
      currentStep = 2; setPhase("planning");
      const candidate = await planDesktopIntegrations();
      if (candidate.source !== next.source || candidate.hosts.length !== 8) throw new Error("integration_plan_source_mismatch");
      setPlan(candidate); setPhase("review");
    } catch {
      setFailedStep(currentStep); setPhase("failed");
      setFailure(currentStep === 1
        ? "Não foi possível confirmar o Runtime e o acesso. Nenhuma configuração de plugin foi alterada."
        : "O Runtime não entregou um plano válido para os oito hosts. Nenhuma configuração foi alterada.");
    } finally {
      operationLock.current = false;
    }
  }

  function acceptResult(result: HostPluginOperationResult) {
    setOutcome(result);
    if (result.snapshot.state === "partial" || result.snapshot.state === "requires_reconcile") {
      setFailedStep(4);
      setFailure("O Runtime registrou um resultado parcial. Use a reconciliação explícita deste recibo antes de uma nova aplicação.");
      setPhase("failed");
    } else {
      setPhase("complete");
    }
  }

  async function apply() {
    if (operationLock.current || busy || blockedWithoutReceipt || phase !== "review" || !plan || !confirmed
      || submittedPlanDigest.current === plan.planDigest) return;
    operationLock.current = true;
    const digest = plan.planDigest;
    submittedPlanDigest.current = digest;
    setConfirmed(false); setFailure(""); setOutcome(null); setPhase("installing");
    try {
      acceptResult(await onApply(digest));
    } catch {
      setFailedStep(3); setPhase("failed");
      setFailure("O Runtime não devolveu um recibo canônico. Consulte o estado antes de repetir qualquer aplicação.");
    } finally {
      operationLock.current = false;
    }
  }

  async function reconcile() {
    if (operationLock.current || busy || !reconcileReceiptId || submittedReconcileId.current === reconcileReceiptId) return;
    operationLock.current = true;
    submittedReconcileId.current = reconcileReceiptId;
    setFailure(""); setPhase("reconciling");
    try {
      acceptResult(await onReconcile(reconcileReceiptId));
    } catch {
      setFailedStep(4); setPhase("failed");
      setFailure("A reconciliação não devolveu um recibo canônico. Nenhuma nova aplicação foi iniciada.");
    } finally {
      operationLock.current = false;
    }
  }

  const heading = phase === "welcome" ? "Um bom começo."
    : phase === "review" ? "Tudo pronto para revisar."
      : phase === "complete" ? preview ? "Prévia concluída." : hostPluginOutcomeLabel(outcome!.snapshot)
        : phase === "failed" ? "Não foi possível concluir."
          : phase === "checking" ? "Conferindo o Runtime…" : phase === "planning" ? "Preparando suas integrações…"
            : phase === "installing" ? "Configurando o Simplicio…" : "Reconciliando o recibo…";

  return <div className={`setup-layout ${phase === "welcome" ? "setup-intro" : ""}`}>
    <header className="entry-header"><Brand /><span className="setup-context">{preview ? "Demonstração · sem instalação real" : "Instalação guiada"}</span></header>
    {phase !== "welcome" && <div className="setup-status-header"><div className="setup-status-inner">
      <div className="setup-progress-caption" role="status" aria-atomic="true">
        <span className={"setup-current-stage" + (phase === "failed" ? " is-failed" : "")}>{pending ? <span className="setup-spinner" aria-hidden="true" /> : <Glyph name={phase === "failed" ? "attention" : phase === "complete" ? "check" : "shield"} size={17} />}{currentStage?.label ?? (phase === "review" ? "Aguardando sua confirmação" : "Recibo recebido do Runtime")}</span>
        <span>{completed} de 4 etapas concluídas</span>
      </div>
      <progress className="setup-progress" value={completed} max={4} aria-label="Etapas da configuração concluídas" />
    </div></div>}
    <main className="setup-main" ref={content}>
      {phase === "welcome" ? <div className="setup-welcome">
        <img src="/icon.png" width="72" height="72" alt="" />
        <span className="setup-wordmark">SIMPLICIO</span>
        <h1>{heading}</h1>
        <p>Seu Runtime e seus apps,<br />trabalhando juntos.</p>
        <button className="button entry-primary" type="button" disabled={busy || blockedWithoutReceipt || runtimePending} onClick={() => void prepare()}>Configurar Simplicio<Glyph name="arrow" size={18} /></button>
        {(blockedWithoutReceipt || runtimePending) && <><div className="setup-failure setup-recovery-note" role="alert"><strong>{applicationError || "O Runtime possui uma operação de plugin pendente."}</strong><p>Uma leitura de estado não instala, verifica nem reconcilia plugins. A reconciliação abaixo usa somente o identificador escolhido pelo Runtime.</p></div>{reconcileReceiptId
          ? <button className="button button-primary" type="button" disabled={busy} onClick={() => void reconcile()}>Reconciliar recibo</button>
          : <button className="button button-secondary" type="button" disabled={busy} onClick={onDiagnostics}>Abrir diagnóstico</button>}</>}
        <button className="text-button" type="button" disabled={busy} onClick={onFinish}>Agora não</button>
        <span className="entry-caption">Primeiro, vamos conferir o que já existe. Login e consultas não instalam plugins.</span>
      </div> : <div className="setup-body">
        <div className={`setup-heading ${phase === "failed" ? "is-failed" : ""}`}>
          <span className="eyebrow">{phase === "complete" ? "Próximo passo: abrir seus clientes" : "Configure uma vez. Use nos seus apps."}</span>
          <h1 ref={headingElement} tabIndex={-1}>{heading}</h1>
          <p>{phase === "review" ? `O Runtime incluiu ${plan?.hosts.length ?? 0} hosts no plano. Revise cada resultado antes de autorizar.`
            : phase === "complete" ? "O painel usa diretamente o recibo devolvido pelo Runtime. Um host aplicado sem leitura confiável permanece não verificado."
              : "Somente o Runtime mantém recibos, estado pendente e autoridade de reconciliação."}</p>
        </div>
        <ol className="setup-steps" aria-label="Etapas da instalação">{steps.map((step, index) => <li key={step.label} data-state={step.state} aria-current={step.state === "running" ? "step" : undefined}>
          <span className="setup-step-icon" aria-hidden="true">{step.state === "running" ? <span className="setup-spinner" /> : step.state === "complete" ? <Glyph name="check" size={16} /> : step.state === "failed" ? <Glyph name="close" size={16} /> : index + 1}</span>
          <div><strong>{step.label}</strong><p>{step.detail}</p></div>
          <span className="setup-step-status">{({ pending: "Pendente", running: "Em andamento", complete: "Concluída", failed: "Falhou" })[step.state]}</span>
        </li>)}</ol>
        {phase === "review" && plan && <section className="setup-review" aria-label="Plano de instalação">
          <h2 ref={reviewHeading} tabIndex={-1}>O que será configurado</h2>
          <ul>{plan.hosts.map((host) => <li key={host.host}><span>{HOST_LABELS[host.host]}</span><strong>{integrationChangeLabel(host)}</strong></li>)}</ul>
          <p>Estes são os oito hosts com instalação nativa ou plugin suportado. Os demais clientes continuam como integrações MCP ou guiadas e não são apresentados como plugins nativos.</p>
          <label className="setup-consent"><input type="checkbox" checked={confirmed} disabled={locked || blockedWithoutReceipt} onChange={(event) => setConfirmed(event.target.checked)} />Autorizo o Runtime a aplicar exatamente o plano identificado por este resumo.</label>
        </section>}
        {receipt && <section className="setup-review" aria-label="Resultado dos plugins">
          <h2>Resultado do Runtime</h2>
          <ul>{receipt.hosts.map((host) => <li key={host.host}><span>{HOST_LABELS[host.host]}</span><strong>{resultLabel(host)}</strong></li>)}</ul>
        </section>}
        {!receipt && projected && projected.hosts.length > 0 && <section className="setup-review" aria-label="Estado dos plugins">
          <h2>Último estado do Runtime</h2>
          <ul>{projected.hosts.map((host) => <li key={host.host}><span>{HOST_LABELS[host.host]}</span><strong>{resultLabel(host)}</strong></li>)}</ul>
        </section>}
        {phase === "failed" && <div className="setup-failure" role="alert"><strong>{applicationError || failure}</strong><p>{reconcileReceiptId ? "A reconciliação consulta e atualiza somente o recibo selecionado; ela não repete a aplicação." : "Consulte o estado do Runtime antes de preparar outro plano."}</p></div>}
        {phase === "complete" && receipt && <div className="setup-success" role="status"><Glyph name="check" size={20} /><p>{preview ? "Esta é uma demonstração. Nenhum arquivo foi alterado." : `${hostPluginOutcomeLabel(receipt)}. O Desktop não executou uma segunda leitura, verificação ou aplicação.`}</p></div>}
        {showDetails && <section ref={detailsElement} className="setup-details" id="setup-details" aria-label="Detalhes da configuração">
          <p>Origem: {preview ? "prévia no navegador" : "Runtime local"} · Versão {snapshot.runtime.version}</p>
          {plan && <><p>Versão do plugin: {plan.pluginVersion}</p><p className="setup-digest">Plano autorizado: <code>{plan.planDigest}</code></p></>}
          {receipt && <p className="setup-digest">Recibo canônico: <code>{receipt.receiptDigest}</code></p>}
          <p>Senhas, tokens, caminhos pessoais, backups, comandos e saídas brutas não são exibidos.</p>
        </section>}
      </div>}
    </main>
    {phase !== "welcome" && <div className="setup-actionbar"><div className="setup-footer-inner">
      {pending && <p className="setup-pending-note">{phase === "installing" ? "Aguardando um único resultado do Runtime. A ação não será repetida automaticamente." : phase === "reconciling" ? "Reconciliando explicitamente o recibo selecionado…" : "Aguardando a resposta do Runtime local…"}</p>}
      <div className="setup-controls">
        <button className="text-button" type="button" aria-expanded={showDetails} aria-controls="setup-details" onClick={() => setShowDetails((value) => !value)}><Glyph name="chevron" size={14} />{showDetails ? "Ocultar detalhes" : "Mostrar detalhes"}</button>
        <div>{phase === "review" && <>
          <button className="button button-secondary" type="button" onClick={() => { reviewHeading.current?.scrollIntoView({ block: "start" }); reviewHeading.current?.focus({ preventScroll: true }); }}>Revisar destinos</button>
          <button className="button button-primary" type="button" disabled={locked || blockedWithoutReceipt || !confirmed} onClick={() => void apply()}>{preview ? "Simular configuração" : "Instalar e conectar"}<Glyph name="arrow" size={16} /></button>
        </>}
        {phase === "failed" && reconcileReceiptId && !reconcileConsumed && <button className="button button-primary" type="button" disabled={locked} onClick={() => void reconcile()}>Reconciliar recibo</button>}
        {phase === "failed" && reconcileConsumed && <button className="button button-secondary" type="button" disabled={locked} onClick={onDiagnostics}>Consultar estado no diagnóstico</button>}
        {phase === "failed" && !blockedWithoutReceipt && !reconcileReceiptId && applicationRecovery === "review" && <button className="button button-primary" type="button" disabled={locked} onClick={() => void prepare()}>Revisar novamente</button>}
        {phase === "complete" && <button className="button button-primary" type="button" onClick={onFinish}>Abrir Simplicio<Glyph name="arrow" size={16} /></button>}
        {phase === "failed" && !reconcileReceiptId && <button className="button button-secondary" type="button" disabled={locked} onClick={onDiagnostics}>Abrir diagnóstico</button>}
        {phase !== "complete" && <button className="button button-secondary" type="button" disabled={locked} onClick={onFinish}>Voltar ao app</button>}
        </div>
      </div>
    </div></div>}
    <footer className="entry-footer"><Glyph name="shield" size={14} />Runtime local · Consentimento por digest · Recibo canônico</footer>
  </div>;
}
