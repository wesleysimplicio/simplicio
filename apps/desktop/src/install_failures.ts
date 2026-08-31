const RECONCILIATION_REQUIRED = "Pode haver alterações parciais. Novas aplicações estão bloqueadas nesta sessão. Consulte o diagnóstico para esclarecer o resultado; atualizar ou reiniciar o app não confirma a conclusão.";

export type InstallFailureRecovery = "review" | "wait" | "reconcile" | "refresh";

/** A recovery hint, never authorization to repeat a native side effect. */
export function installFailureRecovery(error: unknown): InstallFailureRecovery {
  switch (nativeCode(error)) {
    case "integration_preflight_unavailable":
    case "integration_plan_changed_review_again":
    case "integration_install_not_started":
      return "review";
    case "integration_install_busy":
      return "wait";
    case "integration_install_applied_snapshot_unavailable":
      return "refresh";
    default:
      return "reconcile";
  }
}

const MESSAGES: Readonly<Record<string, string>> = {
  integration_preflight_unavailable: "Não foi possível confirmar o Runtime e o plano antes da instalação. O instalador não foi iniciado. Consulte o diagnóstico e revise um novo plano antes de confirmar novamente.",
  integration_plan_changed_review_again: "O plano mudou. Revise a configuração novamente antes de aplicar.",
  integration_install_busy: "Uma instalação já está em andamento. Aguarde a conclusão; não inicie outra aplicação.",
  integration_install_not_started: "O instalador não foi iniciado. Revise um novo plano e confirme a configuração antes de tentar novamente.",
  integration_install_timeout: `O instalador ultrapassou o prazo de execução sem confirmar a aplicação. ${RECONCILIATION_REQUIRED}`,
  integration_install_output_unavailable: `Não foi possível obter o resultado do instalador. ${RECONCILIATION_REQUIRED}`,
  integration_install_no_exit_code: `O instalador terminou sem um código de saída confirmado. ${RECONCILIATION_REQUIRED}`,
  integration_install_invalid_json: `O instalador devolveu uma resposta inválida. ${RECONCILIATION_REQUIRED}`,
  integration_install_response_too_large: `A resposta do instalador ultrapassou o limite permitido. ${RECONCILIATION_REQUIRED}`,
  integration_install_stderr_too_large: `A saída de diagnóstico do instalador ultrapassou o limite permitido. ${RECONCILIATION_REQUIRED}`,
  integration_install_receipt_unconfirmed: `O Runtime não confirmou um recibo de instalação completo. ${RECONCILIATION_REQUIRED}`,
  integration_install_cleanup_unconfirmed: `Não foi possível confirmar o encerramento do processo do instalador. ${RECONCILIATION_REQUIRED}`,
  integration_install_reconciliation_required: `Uma tentativa anterior ainda tem resultado incerto. ${RECONCILIATION_REQUIRED}`,
  integration_install_applied_snapshot_unavailable: "O instalador confirmou a aplicação, mas não foi possível consultar o estado final do Runtime. Consulte novamente o diagnóstico para verificar as configurações; não reinstale para repetir essa consulta.",
};

/** Translate only closed native codes; never reflect stdout, stderr or user paths. */
export function installFailureMessage(error: unknown): string {
  const code = nativeCode(error);
  if (code.length <= 100 && Object.prototype.hasOwnProperty.call(MESSAGES, code)) return MESSAGES[code];
  if (code.length <= 100) {
    const match = /^integration_install_exit_code:(-?\d{1,11})$/.exec(code);
    if (match) {
      const exitCode = Number(match[1]);
      if (Number.isInteger(exitCode) && exitCode !== 0 && exitCode >= -2_147_483_648 && exitCode <= 2_147_483_647) {
        return `O instalador encerrou com código ${exitCode}. ${RECONCILIATION_REQUIRED}`;
      }
    }
  }
  return "O Runtime não confirmou a instalação completa. Não repita a aplicação até esclarecer o resultado. Pode haver alterações parciais; consultar o diagnóstico ou reiniciar o app não confirma a conclusão.";
}

function nativeCode(error: unknown): string {
  const code = typeof error === "string" ? error : error instanceof Error ? error.message : "";
  return typeof code === "string" && code.length <= 100 ? code : "";
}
