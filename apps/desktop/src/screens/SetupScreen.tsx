import { useEffect, useRef, useState } from "react";
import { planDesktopIntegrations, refreshDesktopSnapshot } from "../bridge";
import { Brand, Glyph } from "../components/Brand";
import type { DesktopSnapshot } from "../contracts";
import { integrationTargetsVerified, type IntegrationPlan } from "../integration_setup";
import type { InstallFailureRecovery } from "../install_failures";
import { canConfigureRuntime, setupStages, type SetupPhase, type SetupStep } from "../setup_flow";

export function SetupScreen({ snapshot, busy, applicationError, applicationRecovery, onSnapshot, onApply, onVerificationFailure, onFinish, onDiagnostics }: {
  snapshot: DesktopSnapshot;
  busy: boolean;
  applicationError: string | null;
  applicationRecovery?: InstallFailureRecovery;
  onSnapshot: (snapshot: DesktopSnapshot) => void;
  onApply: (digest: string) => Promise<boolean>;
  onVerificationFailure?: () => void;
  onFinish: () => void;
  onDiagnostics: () => void;
}) {
  const [phase, setPhase] = useState<SetupPhase>("welcome");
  const [failedStep, setFailedStep] = useState<SetupStep>(1);
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [applicationConfirmed, setApplicationConfirmed] = useState(false);
  const [verifiedPlan, setVerifiedPlan] = useState<IntegrationPlan | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [failure, setFailure] = useState("");
  const operationLock = useRef(false);
  const content = useRef<HTMLElement>(null);
  const headingElement = useRef<HTMLHeadingElement>(null);
  const detailsElement = useRef<HTMLElement>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const pending = ["checking", "planning", "installing", "verifying"].includes(phase);
  const locked = busy || pending;
  const preview = snapshot.source === "preview";
  const recovery = phase === "failed" && failedStep === 4 && !preview ? "refresh"
    : applicationRecovery ?? (phase === "failed" && failedStep === 3 && !preview ? "reconcile" : undefined);
  const reviewBlocked = recovery !== undefined && recovery !== "review";
  const recoveryGuidance = recovery === "wait"
    ? "Não inicie outra aplicação enquanto a instalação estiver em andamento. Consulte o diagnóstico para acompanhar o estado."
    : recovery === "refresh"
      ? "Atualize somente o diagnóstico para conferir o resultado. Uma consulta de estado não reinstala o Simplicio nem autoriza outra aplicação."
      : "Novas aplicações estão bloqueadas nesta sessão. Consulte o diagnóstico para esclarecer o resultado; atualizar ou reiniciar o app não confirma a conclusão.";
  const steps = setupStages(phase, failedStep);
  const completed = steps.filter((step) => step.state === "complete").length;
  const currentStage = steps.find((step) => step.state === "running" || step.state === "failed");

  useEffect(() => {
    if (applicationRecovery === "refresh" && phase === "failed" && failedStep === 3) {
      setApplicationConfirmed(true);
      setFailedStep(4);
    }
  }, [applicationRecovery, phase, failedStep]);

  useEffect(() => { if (reviewBlocked) setConfirmed(false); }, [reviewBlocked]);

  useEffect(() => {
    content.current?.scrollTo({ top: 0 });
    if (phase === "review" || phase === "complete" || phase === "failed") {
      headingElement.current?.focus({ preventScroll: true });
    }
  }, [phase]);

  useEffect(() => {
    if (showDetails) detailsElement.current?.scrollIntoView({ block: "nearest" });
  }, [showDetails]);

  async function prepare() {
    if (operationLock.current || busy || reviewBlocked) return;
    operationLock.current = true;
    setPlan(null); setConfirmed(false); setFailure(""); setPhase("checking");
    setApplicationConfirmed(false); setVerifiedPlan(null);
    let currentStep: SetupStep = 1;
    try {
      const next = await refreshDesktopSnapshot();
      onSnapshot(next);
      if (!canConfigureRuntime(next)) throw new Error("runtime_not_ready");
      currentStep = 2; setPhase("planning");
      const candidate = await planDesktopIntegrations();
      if (candidate.source !== next.source) throw new Error("integration_plan_source_mismatch");
      if (new Set(candidate.changes.map((row) => row.label)).size !== candidate.changes.length) throw new Error("integration_plan_ambiguous_targets");
      setPlan(candidate); setPhase("review");
    } catch {
      setFailedStep(currentStep); setPhase("failed");
      setFailure(currentStep === 1 ? "Não foi possível confirmar o Runtime e o acesso. Verifique a conexão e o diagnóstico antes de continuar. Nenhuma configuração foi alterada."
        : "O Runtime não entregou um plano válido. Nenhuma configuração foi alterada; você pode revisar novamente.");
    } finally { operationLock.current = false; }
  }

  async function apply() {
    if (operationLock.current || busy || reviewBlocked || phase !== "review" || !plan || !confirmed) return;
    operationLock.current = true;
    const reviewed = plan;
    const digest = reviewed.planDigest;
    setConfirmed(false); setFailure(""); setPhase("installing");
    setApplicationConfirmed(false); setVerifiedPlan(null);
    let currentStep: SetupStep = 3;
    try {
      if (!await onApply(digest)) throw new Error("installation_not_confirmed");
      setApplicationConfirmed(true);
      currentStep = 4; setPhase("verifying");
      const next = await refreshDesktopSnapshot();
      onSnapshot(next);
      if (!canConfigureRuntime(next)) throw new Error("runtime_verification_failed");
      const observed = await planDesktopIntegrations();
      if (observed.source !== next.source || !integrationTargetsVerified(reviewed, observed)) throw new Error("integration_targets_unconfirmed");
      setVerifiedPlan(observed);
      setPhase("complete");
    } catch {
      setFailedStep(currentStep); setPhase("failed");
      if (currentStep === 4 && !preview) onVerificationFailure?.();
      setFailure(currentStep === 3 ? "A instalação não foi confirmada. Pode haver alterações parciais. Revise um novo plano antes de tentar novamente."
        : preview ? "A demonstração não confirmou os destinos do plano revisado. Nenhum arquivo foi alterado."
          : "O plano foi aplicado, mas a verificação final falhou. Os destinos do plano revisado não foram confirmados sem mudanças pendentes. Consulte o diagnóstico; nenhuma reinstalação foi iniciada.");
    } finally { operationLock.current = false; }
  }

  const heading = phase === "welcome" ? "Um bom começo."
    : phase === "review" ? "Tudo pronto para revisar."
      : phase === "complete" ? preview ? "Prévia concluída." : "Configuração concluída."
        : phase === "failed" ? "Não foi possível concluir."
          : phase === "checking" ? "Conferindo o Runtime…" : phase === "planning" ? "Preparando suas integrações…"
            : phase === "installing" ? "Configurando o Simplicio…" : "Verificando o resultado…";

  return <div className={`setup-layout ${phase === "welcome" ? "setup-intro" : ""}`}>
    <header className="entry-header"><Brand /><span className="setup-context">{preview ? "Demonstração · sem instalação real" : "Instalação guiada"}</span></header>
    {phase !== "welcome" && <div className="setup-status-header">
      <div className="setup-status-inner">
        <div className="setup-progress-caption" role="status" aria-atomic="true">
          <span className={"setup-current-stage" + (phase === "failed" ? " is-failed" : "")}>{pending ? <span className="setup-spinner" aria-hidden="true" /> : <Glyph name={phase === "failed" ? "attention" : phase === "complete" ? "check" : "shield"} size={17} />}
            {currentStage?.label ?? (phase === "review" ? "Aguardando sua confirmação" : "Configuração verificada")}
          </span>
          <span>{completed} de 4 etapas concluídas</span>
        </div>
        <progress className="setup-progress" value={completed} max={4} aria-label="Etapas da configuração concluídas" />
      </div>
    </div>}
    <main className="setup-main" ref={content}>
      {phase === "welcome" ? <div className="setup-welcome">
        <img src="/icon.png" width="72" height="72" alt="" />
        <span className="setup-wordmark">SIMPLICIO</span>
        <h1>{heading}</h1>
        <p>Seu Runtime e seus apps,<br />trabalhando juntos.</p>
        <button className="button entry-primary" type="button" disabled={busy || reviewBlocked} onClick={() => void prepare()}>Configurar Simplicio<Glyph name="arrow" size={18} /></button>
        {reviewBlocked && <>
          <div className="setup-failure setup-recovery-note" role="alert"><strong>{applicationError || (recovery === "refresh" ? "A aplicação já foi confirmada pelo Runtime." : recovery === "wait" ? "Aguarde a instalação em andamento." : "O resultado da instalação ainda precisa ser esclarecido.")}</strong><p>{recoveryGuidance}</p></div>
          <button className="button button-secondary" type="button" disabled={busy} onClick={onDiagnostics}>{recovery === "refresh" ? "Atualizar diagnóstico" : "Abrir diagnóstico"}</button>
        </>}
        <button className="text-button" type="button" disabled={busy} onClick={onFinish}>Agora não</button>
        <span className="entry-caption">Primeiro, vamos conferir o que já existe. Nenhum arquivo será alterado sem sua confirmação.</span>
      </div> : <div className="setup-body">
        <div className={`setup-heading ${phase === "failed" ? "is-failed" : ""}`}>
          <span className="eyebrow">{phase === "complete" ? "Próximo passo: abrir seus clientes" : "Configure uma vez. Use nos seus apps."}</span>
          <h1 ref={headingElement} tabIndex={-1}>{heading}</h1>
          <p>{phase === "review" ? `${plan?.changes.filter((row) => row.changed).length ?? 0} alterações propostas. Revise os destinos abaixo antes de aplicar.`
            : phase === "complete" ? "Abra uma nova sessão nos clientes para confirmar o handshake MCP. Registro não significa conexão ativa."
              : "O Runtime que acompanha o app gerencia a instalação local e o registro nos clientes detectados."}</p>
        </div>
        <ol className="setup-steps" aria-label="Etapas da instalação">{steps.map((step, index) => <li key={step.label} data-state={step.state} aria-current={step.state === "running" ? "step" : undefined}>
          <span className="setup-step-icon" aria-hidden="true">{step.state === "running" ? <span className="setup-spinner" /> : step.state === "complete" ? <Glyph name="check" size={16} /> : step.state === "failed" ? <Glyph name="close" size={16} /> : index + 1}</span>
          <div><strong>{step.label}</strong><p>{step.detail}</p></div>
          <span className="setup-step-status">{({ pending: "Pendente", running: "Em andamento", complete: "Concluída", failed: "Falhou" })[step.state]}</span>
        </li>)}</ol>
        {phase === "review" && plan && <section className="setup-review" aria-label="Plano de instalação">
          <h2 ref={reviewHeading} tabIndex={-1}>O que será configurado</h2>
          <ul>{plan.changes.map((row, index) => <li key={`${row.label}-${index}`}><span>{row.label}</span><strong>{row.changed ? row.exists ? "Atualizar" : "Criar" : "Já configurado"}</strong></li>)}</ul>
          {plan.changes.length === 0 && <p>Nenhuma mudança foi proposta pelo Runtime.</p>}
          <p>MCP e hooks dos clientes detectados, com backups. Plugins de marketplace e permissões dependem de cada host. Este fluxo não altera o PATH nem inicia um serviço global.</p>
          <label className="setup-consent"><input type="checkbox" checked={confirmed} disabled={locked || reviewBlocked} onChange={(event) => setConfirmed(event.target.checked)} />Autorizo o Runtime a aplicar este plano de instalação e registro.</label>
        </section>}
        {phase === "review" && reviewBlocked && <div className="setup-failure" role="alert"><strong>{applicationError || "A aplicação não está disponível neste estado."}</strong><p>{recoveryGuidance}</p></div>}
        {phase === "failed" && <div className="setup-failure" role="alert"><strong>{applicationError && (failedStep === 3 || applicationRecovery === "refresh") ? applicationError : failure}</strong><p>{reviewBlocked ? recoveryGuidance : "Revisar novamente apenas prepara um novo plano. Nenhuma instalação será repetida automaticamente."}</p></div>}
        {phase === "complete" && <div className="setup-success" role="status"><Glyph name="check" size={20} /><p>{preview ? "Esta é uma demonstração. Nenhum arquivo foi alterado." : "O Runtime confirmou a aplicação, e uma nova leitura confirmou os destinos preexistentes ou alterados do plano revisado sem mudanças pendentes. A conexão de cada cliente ainda depende do handshake."}</p></div>}
        {showDetails && <section ref={detailsElement} className="setup-details" id="setup-details" aria-label="Detalhes da configuração">
          <p>Origem: {preview ? "prévia no navegador" : "Runtime local"} · Versão {snapshot.runtime.version}</p>
          <p>Estado do Runtime: {snapshot.runtime.state}. Cada etapa só é concluída após a resposta correspondente; este painel não estima tempos ou downloads.</p>
          {plan && <p className="setup-digest">Plano revisado: <code>{plan.planDigest}</code></p>}
          {applicationConfirmed && <p>{preview ? "Aplicação simulada." : "Aplicação confirmada pelo Runtime."} Conferência dos destinos: {verifiedPlan ? "confirmada por nova leitura do plano." : "ainda não confirmada."}</p>}
          {verifiedPlan && <p className="setup-digest">Plano após a aplicação: <code>{verifiedPlan.planDigest}</code></p>}
          <p>Senhas, tokens de autenticação, caminhos pessoais e conteúdo de arquivos não são exibidos neste painel.</p>
        </section>}
      </div>}
    </main>
    {phase !== "welcome" && <div className="setup-actionbar"><div className="setup-footer-inner">
        {pending && <p className="setup-pending-note">{phase === "installing" ? "Aguarde a resposta do Runtime. Esta operação não oferece cancelamento seguro depois de iniciada." : "Aguardando a resposta do Runtime local…"}</p>}
        <div className="setup-controls">
          <button className="text-button" type="button" aria-expanded={showDetails} aria-controls="setup-details" onClick={() => setShowDetails((value) => !value)}><Glyph name="chevron" size={14} />{showDetails ? "Ocultar detalhes" : "Mostrar detalhes"}</button>
          <div>{phase === "review" && <>
            <button className="button button-secondary" type="button" onClick={() => { reviewHeading.current?.scrollIntoView({ block: "start" }); reviewHeading.current?.focus({ preventScroll: true }); }}>Revisar destinos</button>
            <button className="button button-primary" type="button" disabled={locked || reviewBlocked || !confirmed} onClick={() => void apply()}>{preview ? "Simular configuração" : "Instalar e conectar"}<Glyph name="arrow" size={16} /></button>
          </>}
            {phase === "failed" && !reviewBlocked && <button className="button button-primary" type="button" disabled={locked} onClick={() => void prepare()}>Revisar novamente</button>}
            {phase === "complete" && <button className="button button-primary" type="button" onClick={onFinish}>Abrir Simplicio<Glyph name="arrow" size={16} /></button>}
            {(phase === "failed" || reviewBlocked) && <button className="button button-secondary" type="button" disabled={locked} onClick={onDiagnostics}>{recovery === "refresh" ? "Atualizar diagnóstico" : "Abrir diagnóstico"}</button>}
            {phase !== "complete" && <button className="button button-secondary" type="button" disabled={locked} onClick={onFinish}>Voltar ao app</button>}
          </div>
        </div>
    </div></div>}
    <footer className="entry-footer"><Glyph name="shield" size={14} />Runtime local · Configuração revisada · Evidência verificável</footer>
  </div>;
}
